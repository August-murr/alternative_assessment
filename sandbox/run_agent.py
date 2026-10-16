"""Run Claude Code autonomously on a task inside a Modal sandbox and capture everything it does.

    python -m sandbox.run_agent [--task tasks/olist] [--model ...] [--effort low] [--max-turns N]
                                [--max-budget-usd X] [--no-eval]

A task is a directory with PROMPT.md and task.yaml (see tasks/olist/). PROMPT.md may use
${placeholders} filled from config.yaml (e.g. ${train_timeout_s}).

Produces runs/<timestamp>-<task>/:
  transcript.jsonl   raw stream-json events (replay: python -m sandbox.trace <file>)
  stderr.txt         claude's stderr
  session/           Claude Code's own session log(s) from ~/.claude/projects
  submission/        whatever the agent left in /workspace/submission
  run.json           config snapshot, exit code, sandbox id, timings
  eval.json          result of the network-blocked evaluation (if the task has an evaluator)
  SUMMARY.md         one-page summary of the run
"""

import argparse
import io
import json
import signal
import tarfile
import time
from datetime import datetime
from pathlib import Path
from string import Template

from common.config import ROOT, Config, env, load_config  # must precede `import modal` (loads .env)

import modal

from sandbox import trace
from sandbox.evaluate import evaluate, load_task
from sandbox.image import ML_PACKAGES, TRAIN_DATA_DIR, WORKDIR, agent_image
from sandbox.summary import write_summary

SUBMISSION_DIR = f"{WORKDIR}/submission"
SESSION_DIR = "/root/.claude/projects"


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
    local_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        tar.extractall(local_dir, filter="data")
    return True


def render_prompt(task_dir: Path, cfg: Config) -> str:
    e = cfg.evaluation
    values = {
        "train_timeout_s": e.train_timeout_s, "train_timeout_min": e.train_timeout_s // 60,
        "predict_timeout_s": e.predict_timeout_s, "predict_timeout_min": e.predict_timeout_s // 60,
        "eval_cpu": f"{e.cpu:g}", "eval_memory_gb": f"{e.memory_mb / 1024:g}",
        "agent_cpu": f"{cfg.modal.cpu:g}", "agent_memory_gb": f"{cfg.modal.memory_mb / 1024:g}",
        "agent_timeout_min": cfg.modal.timeout_s // 60,
        "train_data_dir": TRAIN_DATA_DIR, "ml_packages": ", ".join(ML_PACKAGES),
    }
    return Template((task_dir / "PROMPT.md").read_text()).safe_substitute(values)


def claude_command(prompt: str, args: argparse.Namespace, cfg: Config) -> list[str]:
    cmd = [
        "claude", "-p", prompt,
        "--model", args.model,
        "--output-format", "stream-json", "--verbose",
        "--dangerously-skip-permissions",
    ]
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


def _exit_on_sigterm(signum, frame):
    raise SystemExit(143)  # run the `finally` blocks so sandboxes get terminated


def main() -> None:
    signal.signal(signal.SIGTERM, _exit_on_sigterm)
    cfg = load_config()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", type=Path, default=cfg.agent.task_dir)
    parser.add_argument("--model", default=cfg.agent.model)
    parser.add_argument("--effort", default=cfg.agent.effort)
    parser.add_argument("--max-turns", type=int, default=cfg.agent.max_turns)
    parser.add_argument("--max-budget-usd", type=float, default=cfg.agent.max_budget_usd)
    parser.add_argument("--no-eval", action="store_true", help="skip the network-blocked evaluation")
    args = parser.parse_args()

    task_dir = args.task.resolve()
    task = load_task(task_dir)
    prompt = render_prompt(task_dir, cfg)
    run_dir = ROOT / "runs" / f"{datetime.now():%Y%m%d-%H%M%S}-{task_dir.name}"
    run_dir.mkdir(parents=True)
    (run_dir / "prompt.md").write_text(prompt)

    workspace_files = {"TASK.md": run_dir / "prompt.md"}
    for name in task.get("workspace_files", []):
        workspace_files[Path(name).name] = task_dir / name
    image = agent_image(
        cfg.agent.claude_code_version,
        train_dir=cfg.data.processed_dir / "train" if task.get("train_data") else None,
        workspace_files=workspace_files,
    )

    app = modal.App.lookup(cfg.modal.app_name, create_if_missing=True)
    print(f"building image / starting sandbox (cpu={cfg.modal.cpu}, mem={cfg.modal.memory_mb}MiB) ...")
    sb = modal.Sandbox.create(
        app=app, image=image, cpu=cfg.modal.cpu, memory=cfg.modal.memory_mb,
        timeout=cfg.modal.timeout_s, secrets=[claude_secret()], workdir=WORKDIR,
    )
    print(f"sandbox {sb.object_id}\ndashboard: {sb.get_dashboard_url()}\nrun dir: {run_dir}\n")

    cmd = claude_command(prompt, args, cfg)
    sandbox_env = {
        # Claude Code refuses --dangerously-skip-permissions as root otherwise; the Modal sandbox is the boundary.
        "IS_SANDBOX": "1",
        "EVAL_TRAIN_TIMEOUT_S": str(cfg.evaluation.train_timeout_s),
        "EVAL_PREDICT_TIMEOUT_S": str(cfg.evaluation.predict_timeout_s),
        **cfg.agent.env,
    }
    started = time.time()
    exit_code, result_event, got_submission = None, None, False
    try:
        sb.exec("mkdir", "-p", SUBMISSION_DIR).wait()
        # stdin from /dev/null, otherwise claude -p waits 3s for piped input.
        proc = sb.exec("bash", "-c", 'exec "$@" < /dev/null', "_", *cmd, env=sandbox_env, timeout=cfg.modal.timeout_s)
        with open(run_dir / "transcript.jsonl", "w") as transcript:
            # Modal yields stdout in arbitrary chunks, not lines: write them verbatim, parse complete lines.
            buffer = ""
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
                    if event.get("type") == "result":
                        result_event = event
            trace.print_line(buffer)
        stderr = proc.stderr.read()
        (run_dir / "stderr.txt").write_text(stderr)
        proc.wait()
        exit_code = proc.returncode
        if exit_code != 0:
            print(f"\nclaude exited with code {exit_code}; stderr tail:\n{stderr[-1500:]}")

        got_submission = pull_dir(sb, SUBMISSION_DIR, run_dir / "submission")
        pull_dir(sb, SESSION_DIR, run_dir / "session")
    finally:
        sb.terminate()

    run_info = {
        "task": str(task_dir.relative_to(ROOT)),
        "model": args.model,
        "effort": args.effort,
        "max_turns": args.max_turns,
        "max_budget_usd": args.max_budget_usd,
        "tools": cfg.agent.tools,
        "agent_env": cfg.agent.env,
        "modal": cfg.modal.model_dump(),
        "evaluation": cfg.evaluation.model_dump(),
        "claude_code_version": cfg.agent.claude_code_version,
        "sandbox_id": sb.object_id,
        "exit_code": exit_code,
        "wall_time_s": round(time.time() - started, 1),
        "submission_files": sorted(str(p.relative_to(run_dir / "submission"))
                                   for p in (run_dir / "submission").rglob("*") if p.is_file()) if got_submission else [],
        "result": {k: result_event.get(k) for k in ("subtype", "is_error", "num_turns", "total_cost_usd", "duration_ms")}
        if result_event else None,
    }
    (run_dir / "run.json").write_text(json.dumps(run_info, indent=2))
    print(f"\nexit={exit_code}  submission={run_info['submission_files']}  -> {run_dir}")

    if got_submission and not args.no_eval:
        evaluate(cfg, app, run_dir, task_dir)
    write_summary(run_dir)
    print(f"summary -> {run_dir / 'SUMMARY.md'}")


if __name__ == "__main__":
    main()
