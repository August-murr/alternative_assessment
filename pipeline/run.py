"""Run Claude Code on a task in a Modal sandbox for N verified iterations (checkpoints).

    python -m pipeline.run [--iterations 3] [--task tasks/olist] [--model ...] [--effort low]

One sandbox and one Claude session per run. For each iteration k:
  1. send PROMPT.md (k=1) or ITERATE.md (k>1, with --resume) and stream the agent's work live
  2. verify: run `validate-submission` ourselves; if it fails, send FIX.md (up to max_fix_attempts)
  3. snapshot /workspace/submission to checkpoints/cp_<k>/, with a diff against the previous one
  4. evaluate the checkpoint in a network-blocked sandbox (in the background, while k+1 runs)
The agent never sees test scores. Costs are tracked per checkpoint (see pipeline/costs.py).

Produces runs/<timestamp>-<task>/: transcript.jsonl, session/, checkpoints/cp_<k>/,
progress.csv, cost_curve.png, run.json, SUMMARY.md.
Watch live: python -u -m pipeline.run > runs/live.log 2>&1, then tail -f runs/live.log
"""

import argparse
import difflib
import io
import json
import shutil
import signal
import tarfile
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from string import Template

import yaml

from pipeline.config import ROOT, Config, env, load_config  # must precede `import modal` (loads .env)

import modal

from pipeline.costs import modal_cost, usage_tokens
from pipeline.evaluate import evaluate_submission
from pipeline.report import build_reports
from pipeline.sandbox import trace
from pipeline.sandbox.image import ML_PACKAGES, TRAIN_DATA_DIR, WORKDIR, agent_image

SUBMISSION_DIR = f"{WORKDIR}/submission"
SESSION_DIR = "/root/.claude/projects"
VALIDATION_SUMMARY = "/tmp/validate-submission/summary.json"
DIFF_SUFFIXES = {".py", ".txt", ".md"}


def claude_secret() -> modal.Secret:
    creds = {k: env(k) for k in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY") if env(k)}
    if not creds:
        raise SystemExit("Set CLAUDE_CODE_OAUTH_TOKEN (or ANTHROPIC_API_KEY) in .env")
    return modal.Secret.from_dict(creds)


def pull_dir(sb: modal.Sandbox, remote_dir: str, local_dir: Path) -> bool:
    """Tar a sandbox directory, read it back, and extract locally. Returns False if it doesn't exist."""
    archive = "/tmp/_pull.tar.gz"
    proc = sb.exec("bash", "-c", f"test -d {remote_dir} && tar czf {archive} --exclude=__pycache__ -C {remote_dir} .")
    proc.wait()
    if proc.returncode != 0:
        return False
    data = sb.filesystem.read_bytes(archive)
    if local_dir.exists():
        shutil.rmtree(local_dir)
    local_dir.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        tar.extractall(local_dir, filter="data")
    return True


def push_dir(sb: modal.Sandbox, local_dir: Path, remote_dir: str) -> None:
    """Replace a sandbox directory with a local one (used to roll back to the last good checkpoint)."""
    sb.exec("bash", "-c", f"rm -rf {remote_dir} && mkdir -p {remote_dir}").wait()
    for path in sorted(local_dir.rglob("*")):
        if path.is_file():
            remote = f"{remote_dir}/{path.relative_to(local_dir)}"
            sb.filesystem.make_directory(str(Path(remote).parent))
            sb.filesystem.copy_from_local(path, remote)


def template_values(cfg: Config, iterations: int) -> dict:
    e = cfg.evaluation
    return {
        "iterations": iterations, "remaining": iterations - 1,
        "train_timeout_min": e.train_timeout_s // 60, "predict_timeout_min": e.predict_timeout_s // 60,
        "eval_cpu": f"{e.cpu:g}", "eval_memory_gb": f"{e.memory_mb / 1024:g}",
        "agent_cpu": f"{cfg.modal.cpu:g}", "agent_memory_gb": f"{cfg.modal.memory_mb / 1024:g}",
        "train_data_dir": TRAIN_DATA_DIR, "ml_packages": ", ".join(ML_PACKAGES),
    }


def render(task_dir: Path, name: str, values: dict) -> str:
    return Template((task_dir / name).read_text()).safe_substitute(values)


def claude_command(prompt: str, args: argparse.Namespace, cfg: Config, session_id: str | None) -> list[str]:
    cmd = ["claude", "-p", prompt, "--model", args.model, "--output-format", "stream-json", "--verbose",
           "--dangerously-skip-permissions"]
    if session_id:
        cmd += ["--resume", session_id]
    if cfg.agent.tools:
        # --tools limits what exists; --allowedTools pre-approves them. The approval list is required
        # because CLAUDE_CODE_SUBPROCESS_ENV_SCRUB forces the permission mode back to default.
        cmd += ["--tools", ",".join(cfg.agent.tools), "--allowedTools", ",".join(cfg.agent.tools)]
    if cfg.agent.disable_slash_commands:
        cmd += ["--disable-slash-commands"]
    if args.effort:
        cmd += ["--effort", args.effort]
    if args.max_turns is not None:
        cmd += ["--max-turns", str(args.max_turns)]
    if args.max_budget_usd is not None:
        cmd += ["--max-budget-usd", str(args.max_budget_usd)]
    return cmd


def run_claude(sb: modal.Sandbox, cmd: list[str], sandbox_env: dict, timeout: int, transcript) -> dict:
    """Run one claude -p call, streaming its events to the terminal and the transcript."""
    proc = sb.exec("bash", "-c", 'exec "$@" < /dev/null', "_", *cmd, env=sandbox_env, timeout=timeout)
    result_event, session_id, tool_calls, buffer = None, None, 0, ""
    # Modal yields stdout in arbitrary chunks, not lines: write them verbatim, parse complete lines.
    for chunk in proc.stdout:
        transcript.write(chunk)
        transcript.flush()
        buffer += chunk
        *lines, buffer = buffer.split("\n")
        for line in lines:
            trace.print_line(line)
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            session_id = event.get("session_id") or session_id
            if event.get("type") == "assistant":
                tool_calls += sum(b.get("type") == "tool_use" for b in event.get("message", {}).get("content", []))
            elif event.get("type") == "result":
                result_event = event
    trace.print_line(buffer)
    stderr = proc.stderr.read()
    proc.wait()
    if proc.returncode != 0:
        print(f"\nclaude exited with code {proc.returncode}; stderr tail:\n{stderr[-1500:]}")
    res = result_event or {}
    return {
        "exit_code": proc.returncode, "session_id": session_id, "tool_calls": tool_calls,
        "subtype": res.get("subtype"), "num_turns": res.get("num_turns"), "duration_ms": res.get("duration_ms"),
        "total_cost_usd": res.get("total_cost_usd"), "usage": usage_tokens(res), "stderr_tail": stderr[-2000:],
    }


def validate(sb: modal.Sandbox, sandbox_env: dict) -> dict:
    """Run validate-submission outside Claude (here its network-namespace block works)."""
    proc = sb.exec("validate-submission", env=sandbox_env)
    output = proc.stdout.read() + proc.stderr.read()
    proc.wait()
    try:
        summary = json.loads(sb.filesystem.read_text(VALIDATION_SUMMARY))
    except Exception:  # noqa: BLE001 - validator crashed before writing its summary
        summary = {"passed": False}
    return {
        "passed": proc.returncode == 0 and summary.get("passed", False),
        "scores": summary.get("pseudo_test_scores"),
        "network_isolated": summary.get("network_isolated_by_harness"),
        "output_tail": output[-3000:],
    }


def read_change(cp_sub: Path) -> str:
    path = cp_sub / "CHECKPOINT.md"
    if path.exists():
        for line in path.read_text().splitlines():
            if line.lower().startswith("change:"):
                return line.split(":", 1)[1].strip()
    return ""


def write_diff(prev_sub: Path | None, cur_sub: Path, out: Path) -> dict:
    def files(d: Path | None) -> dict[str, list[str]]:
        if d is None:
            return {}
        return {str(p.relative_to(d)): p.read_text(errors="replace").splitlines(keepends=True)
                for p in sorted(d.rglob("*")) if p.is_file() and p.suffix in DIFF_SUFFIXES}
    old, new = files(prev_sub), files(cur_sub)
    chunks, added, removed = [], 0, 0
    for name in sorted(set(old) | set(new)):
        diff = list(difflib.unified_diff(old.get(name, []), new.get(name, []), f"a/{name}", f"b/{name}"))
        added += sum(l.startswith("+") and not l.startswith("+++") for l in diff)
        removed += sum(l.startswith("-") and not l.startswith("---") for l in diff)
        chunks.extend(diff)
    out.write_text("".join(chunks))
    return {"lines_added": added, "lines_removed": removed}


def _exit_on_sigterm(signum, frame):
    raise SystemExit(143)  # run the `finally` blocks so sandboxes get terminated


def main() -> None:
    signal.signal(signal.SIGTERM, _exit_on_sigterm)
    cfg = load_config()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--iterations", type=int, default=cfg.agent.iterations)
    parser.add_argument("--task", type=Path, default=cfg.agent.task_dir)
    parser.add_argument("--model", default=cfg.agent.model)
    parser.add_argument("--effort", default=cfg.agent.effort)
    parser.add_argument("--max-turns", type=int, default=cfg.agent.max_turns)
    parser.add_argument("--max-budget-usd", type=float, default=cfg.agent.max_budget_usd)
    args = parser.parse_args()

    task_dir = args.task.resolve()
    task = yaml.safe_load((task_dir / "task.yaml").read_text()) or {}
    n = args.iterations
    values = template_values(cfg, n)
    run_dir = ROOT / "runs" / f"{datetime.now():%Y%m%d-%H%M%S}-{task_dir.name}"
    cps_dir = run_dir / "checkpoints"
    cps_dir.mkdir(parents=True)
    first_prompt = render(task_dir, "PROMPT.md", values)
    (run_dir / "prompt.md").write_text(first_prompt)

    workspace_files = {"TASK.md": run_dir / "prompt.md"}
    for name in task.get("workspace_files", []):
        workspace_files[Path(name).name] = task_dir / name
    image = agent_image(cfg.agent.claude_code_version, train_dir=cfg.data.processed_dir / "train",
                        workspace_files=workspace_files)
    sandbox_env = {
        # Claude Code refuses --dangerously-skip-permissions as root otherwise; the Modal sandbox is the boundary.
        "IS_SANDBOX": "1",
        "EVAL_TRAIN_TIMEOUT_S": str(cfg.evaluation.train_timeout_s),
        "EVAL_PREDICT_TIMEOUT_S": str(cfg.evaluation.predict_timeout_s),
        **cfg.agent.env,
    }

    app = modal.App.lookup(cfg.modal.app_name, create_if_missing=True)
    print(f"building image / starting sandbox (cpu={cfg.modal.cpu}, mem={cfg.modal.memory_mb}MiB) ...")
    sb = modal.Sandbox.create(app=app, image=image, cpu=cfg.modal.cpu, memory=cfg.modal.memory_mb,
                              timeout=cfg.modal.timeout_s, secrets=[claude_secret()], workdir=WORKDIR)
    sandbox_started = time.time()
    print(f"sandbox {sb.object_id}\ndashboard: {sb.get_dashboard_url()}\nrun dir: {run_dir}\n")

    checkpoints: list[dict] = []
    evals: dict[int, Future] = {}
    pool = ThreadPoolExecutor(max_workers=2)
    session_id, prev_cum_cost, last_good = None, 0.0, None
    try:
        sb.exec("mkdir", "-p", SUBMISSION_DIR).wait()
        with open(run_dir / "transcript.jsonl", "w") as transcript:
            for k in range(1, n + 1):
                iter_start = sandbox_started if k == 1 else time.time()
                print(f"\n{'=' * 30} iteration {k}/{n} {'=' * 30}")
                if k == 1:
                    prompt = first_prompt
                else:
                    status = (f"Checkpoint {last_good['k']} was saved and verified: `validate-submission` passed with "
                              f"pseudo-test PR-AUC {last_good['validation']['scores']['pr_auc']}.")
                    if last_good["k"] != k - 1:
                        status = (f"Checkpoint {k - 1} failed verification, so /workspace/submission was rolled back "
                                  f"to checkpoint {last_good['k']}. " + status)
                    final = "5. This is the **final iteration**: make `REPORT.md` a complete final report.\n" if k == n else ""
                    prompt = render(task_dir, "ITERATE.md", {**values, "k": k, "status": status, "final_note": final,
                                                             "val_pr_auc": last_good["validation"]["scores"]["pr_auc"]})

                calls = [{"kind": "iterate", **run_claude(sb, claude_command(prompt, args, cfg, session_id), sandbox_env,
                                                           cfg.agent.iteration_timeout_s, transcript)}]
                session_id = calls[-1]["session_id"] or session_id
                print(f"\n--- verifying checkpoint {k} (validate-submission) ---")
                validation = validate(sb, sandbox_env)
                while not validation["passed"] and len(calls) <= cfg.agent.max_fix_attempts:
                    print(f"checkpoint {k} FAILED verification; fix attempt {len(calls)}/{cfg.agent.max_fix_attempts}")
                    fix = render(task_dir, "FIX.md", {"k": k, "error": validation["output_tail"][-2000:]})
                    calls.append({"kind": "fix", **run_claude(sb, claude_command(fix, args, cfg, session_id), sandbox_env,
                                                              cfg.agent.iteration_timeout_s, transcript)})
                    session_id = calls[-1]["session_id"] or session_id
                    validation = validate(sb, sandbox_env)
                print(f"checkpoint {k}: validation {'PASSED' if validation['passed'] else 'FAILED'} {validation['scores'] or ''}")

                cp_dir = cps_dir / f"cp_{k}"
                pull_dir(sb, SUBMISSION_DIR, cp_dir / "submission")
                costs = [c["total_cost_usd"] for c in calls if c["total_cost_usd"] is not None]
                cum_cost = costs[-1] if costs else prev_cum_cost
                cp = {
                    "k": k, "status": "passed" if validation["passed"] else "failed",
                    "fix_attempts": len(calls) - 1, "calls": calls, "validation": validation,
                    "change": read_change(cp_dir / "submission"),
                    "diff": write_diff(last_good and cps_dir / f"cp_{last_good['k']}" / "submission",
                                       cp_dir / "submission", cp_dir / "diff.patch"),
                    "api_cost_cumulative": cum_cost, "api_cost": cum_cost - prev_cum_cost,
                    "agent_seconds": time.time() - iter_start,
                }
                prev_cum_cost = cum_cost
                checkpoints.append(cp)
                if validation["passed"]:
                    last_good = cp
                    evals[k] = pool.submit(evaluate_submission, cfg, app, cp_dir / "submission", cp_dir, True)
                elif last_good is None:
                    print("the first checkpoint failed verification; stopping the run")
                    break
                elif k < n:
                    push_dir(sb, cps_dir / f"cp_{last_good['k']}" / "submission", SUBMISSION_DIR)
        pull_dir(sb, SESSION_DIR, run_dir / "session")
    finally:
        sb.terminate()
        sandbox_seconds = time.time() - sandbox_started
        if checkpoints:  # teardown time belongs to the last checkpoint
            checkpoints[-1]["agent_seconds"] += sandbox_seconds - sum(c["agent_seconds"] for c in checkpoints)

    print("\nwaiting for checkpoint evaluations ...")
    for cp in checkpoints:
        result = evals[cp["k"]].result() if cp["k"] in evals else None
        cp["eval"] = {k: result.get(k) for k in ("passed", "network_blocked", "test_scores", "sandbox_seconds",
                                                 "file_errors", "prediction_errors")} if result else None
        if result:
            cp["eval"]["steps"] = [{s: st[s] for s in ("step", "status", "seconds")} for st in result.get("steps", [])]
        eval_seconds = (result or {}).get("sandbox_seconds", 0.0)
        cp["modal_agent_cost"] = modal_cost(cp["agent_seconds"], cfg.modal.cpu, cfg.modal.memory_mb, cfg.pricing)
        cp["modal_eval_cost"] = modal_cost(eval_seconds, cfg.evaluation.cpu, cfg.evaluation.memory_mb, cfg.pricing)
        cp["total_cost"] = cp["api_cost"] + cp["modal_agent_cost"] + cp["modal_eval_cost"]
        (cps_dir / f"cp_{cp['k']}" / "checkpoint.json").write_text(json.dumps(cp, indent=2))
        scores = (cp["eval"] or {}).get("test_scores") or {}
        print(f"cp_{cp['k']}: test PR-AUC {scores.get('pr_auc', '-')}  cost ${cp['total_cost']:.3f}")
    pool.shutdown()

    run_info = {
        "task": str(task_dir.relative_to(ROOT)), "iterations": n, "model": args.model, "effort": args.effort,
        "max_turns": args.max_turns, "max_budget_usd": args.max_budget_usd, "tools": cfg.agent.tools,
        "agent_env": cfg.agent.env, "modal": cfg.modal.model_dump(), "evaluation": cfg.evaluation.model_dump(),
        "pricing": cfg.pricing.model_dump(), "claude_code_version": cfg.agent.claude_code_version,
        "sandbox_id": sb.object_id, "session_id": session_id, "sandbox_seconds": round(sandbox_seconds, 1),
        "api_cost_total": prev_cum_cost, "checkpoints_passed": sum(c["status"] == "passed" for c in checkpoints),
    }
    (run_dir / "run.json").write_text(json.dumps(run_info, indent=2))
    build_reports(run_dir)
    print(f"\nreports -> {run_dir / 'SUMMARY.md'}")


if __name__ == "__main__":
    main()
