"""Re-run a submission in a fresh sandbox with ALL outbound network blocked, then score it.

    python -m sandbox.evaluate runs/<id> [--task tasks/olist]

Evaluators (chosen by `evaluator:` in tasks/<name>/task.yaml):
  offline_check  run the task's offline_check.sh against the submission (hello task)
  olist          train.py on the full training data, predict.py on the held-out test features,
                 then score preds.csv locally against test_labels.csv (labels never enter a sandbox)
"""

import argparse
import json
import signal
from pathlib import Path

from common.config import ROOT, Config, load_config  # must precede `import modal` (loads .env)

import modal
import pandas as pd
import yaml
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from harness.run_submission import check_files
from sandbox.image import HARNESS_DIR, TEST_DATA_DIR, TRAIN_DATA_DIR, WORKDIR, base_image, eval_image

NETWORK_PROBE = (
    "python -c \"import urllib.request; urllib.request.urlopen('https://api.anthropic.com', timeout=5)\" "
    "&& echo 'NETWORK REACHABLE' || echo 'network blocked'"
)


def load_task(task_dir: Path) -> dict:
    path = task_dir / "task.yaml"
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def _sandbox(cfg: Config, app: modal.App, image: modal.Image) -> modal.Sandbox:
    e = cfg.evaluation
    return modal.Sandbox.create(app=app, image=image, cpu=e.cpu, memory=e.memory_mb, timeout=e.timeout_s,
                                workdir=WORKDIR, block_network=True)


def _upload_submission(sb: modal.Sandbox, submission: Path) -> None:
    for path in sorted(submission.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            remote = f"{WORKDIR}/submission/{path.relative_to(submission)}"
            sb.filesystem.make_directory(str(Path(remote).parent))
            sb.filesystem.copy_from_local(path, remote)


def _probe_network(sb: modal.Sandbox) -> str:
    probe = sb.exec("bash", "-c", NETWORK_PROBE)
    out = probe.stdout.read().strip()
    probe.wait()
    print(f"network probe: {out}")
    return out


def offline_check(cfg: Config, app: modal.App, run_dir: Path, task_dir: Path) -> dict:
    print("\noffline check: starting network-blocked sandbox ...")
    sb = _sandbox(cfg, app, base_image().workdir(WORKDIR))
    try:
        _upload_submission(sb, run_dir / "submission")
        sb.filesystem.copy_from_local(task_dir / "offline_check.sh", f"{WORKDIR}/offline_check.sh")
        probe_out = _probe_network(sb)
        check = sb.exec("bash", f"{WORKDIR}/offline_check.sh", workdir=f"{WORKDIR}/submission")
        stdout, stderr = check.stdout.read(), check.stderr.read()
        check.wait()
    finally:
        sb.terminate()
    result = {
        "sandbox_id": sb.object_id, "network_blocked": probe_out == "network blocked",
        "check_exit_code": check.returncode, "check_stdout": stdout, "check_stderr": stderr,
        "passed": probe_out == "network blocked" and check.returncode == 0,
    }
    (run_dir / "eval.json").write_text(json.dumps(result, indent=2))
    print(f"check exit={check.returncode}\n--- stdout ---\n{stdout}--- stderr ---\n{stderr}")
    print(f"offline check {'PASSED' if result['passed'] else 'FAILED'} -> {run_dir / 'eval.json'}")
    return result


def score(preds: pd.DataFrame, labels: pd.DataFrame) -> dict:
    merged = labels.merge(preds, on="order_id", how="left")
    y, p = merged["is_late"], merged["p_late"]
    return {
        "pr_auc": round(float(average_precision_score(y, p)), 4),
        "roc_auc": round(float(roc_auc_score(y, p)), 4),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "n_orders": len(merged),
        "positive_rate": round(float(y.mean()), 4),  # = PR-AUC of a random model
    }


def olist(cfg: Config, app: modal.App, run_dir: Path, task_dir: Path) -> dict:
    submission = run_dir / "submission"
    processed = cfg.data.processed_dir
    result: dict = {"passed": False}

    file_errors = check_files(submission)
    if file_errors:
        result["file_errors"] = file_errors
        (run_dir / "eval.json").write_text(json.dumps(result, indent=2))
        print(f"evaluation FAILED before running: {file_errors}")
        return result

    requirements = [l.split("#", 1)[0].strip() for l in (submission / "requirements.txt").read_text().splitlines()]
    requirements = [r for r in requirements if r]
    print(f"\nevaluation: building image (extra requirements: {requirements or 'none'}) and starting network-blocked sandbox ...")
    image = eval_image(requirements, train_dir=processed / "train", test_dir=processed / "test_features")
    sb = _sandbox(cfg, app, image)
    print(f"eval sandbox {sb.object_id}")
    try:
        _upload_submission(sb, submission)
        result["network_probe"] = _probe_network(sb)
        e = cfg.evaluation
        proc = sb.exec(
            "python", f"{HARNESS_DIR}/run_submission.py", "--submission", f"{WORKDIR}/submission",
            "--train-dir", TRAIN_DATA_DIR, "--test-dir", TEST_DATA_DIR, "--work-dir", "/tmp/eval",
            "--train-timeout", str(e.train_timeout_s), "--predict-timeout", str(e.predict_timeout_s),
        )
        proc.stdout.read()
        proc.wait()
        run_result = json.loads(sb.filesystem.read_text("/tmp/eval/result.json"))
        result.update(run_result)
        if run_result["passed"]:
            (run_dir / "preds.csv").write_bytes(sb.filesystem.read_bytes("/tmp/eval/preds.csv"))
    finally:
        sb.terminate()

    result["sandbox_id"] = sb.object_id
    result["network_blocked"] = result.get("network_probe") == "network blocked"
    for step in result.get("steps", []):
        print(f"{step['step']}: {step['status']} in {step['seconds']}s (limit {step['timeout_s']}s)")
        if step["status"] != "ok":
            print(f"--- stderr tail ---\n{step['stderr_tail']}")
    for err in result.get("prediction_errors", []):
        print(f"PREDICTION ERROR: {err}")

    if result.get("passed"):
        result["test_scores"] = score(pd.read_csv(run_dir / "preds.csv"), pd.read_csv(processed / "test_labels.csv"))
        print(f"TEST SCORES: {json.dumps(result['test_scores'])}")
    result["passed"] = bool(result.get("passed")) and result["network_blocked"]
    (run_dir / "eval.json").write_text(json.dumps(result, indent=2))
    print(f"evaluation {'PASSED' if result['passed'] else 'FAILED'} -> {run_dir / 'eval.json'}")
    return result


EVALUATORS = {"offline_check": offline_check, "olist": olist}


def evaluate(cfg: Config, app: modal.App, run_dir: Path, task_dir: Path) -> dict | None:
    name = load_task(task_dir).get("evaluator")
    if name is None:
        return None
    return EVALUATORS[name](cfg, app, run_dir, task_dir)


def _exit_on_sigterm(signum, frame):
    raise SystemExit(143)  # run the `finally` blocks so sandboxes get terminated


def main() -> None:
    signal.signal(signal.SIGTERM, _exit_on_sigterm)
    cfg = load_config()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--task", type=Path, help="defaults to the task recorded in run.json")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    task = args.task or Path(json.loads((run_dir / "run.json").read_text())["task"])
    app = modal.App.lookup(cfg.modal.app_name, create_if_missing=True)
    evaluate(cfg, app, run_dir, task if task.is_absolute() else ROOT / task)


if __name__ == "__main__":
    main()
