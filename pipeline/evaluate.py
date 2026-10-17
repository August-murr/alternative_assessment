"""Re-run a submission in a fresh sandbox with ALL outbound network blocked, then score it.

    python -m pipeline.evaluate <submission_dir> [--out DIR]

train.py runs on the full training data, predict.py on the held-out test features, then
preds.csv is scored locally against test_labels.csv. The labels never enter a sandbox.
Writes <out>/eval.json and <out>/preds.csv.
"""

import argparse
import json
import signal
import time
from pathlib import Path

from pipeline.config import Config, load_config  # must precede `import modal` (loads .env)

import modal
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from pipeline.harness.run_submission import check_files
from pipeline.sandbox.image import HARNESS_DIR, TEST_DATA_DIR, TRAIN_DATA_DIR, WORKDIR, eval_image

NETWORK_PROBE = (
    "python -c \"import urllib.request; urllib.request.urlopen('https://api.anthropic.com', timeout=5)\" "
    "&& echo 'NETWORK REACHABLE' || echo 'network blocked'"
)


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


def _upload_submission(sb: modal.Sandbox, submission: Path) -> None:
    for path in sorted(submission.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            remote = f"{WORKDIR}/submission/{path.relative_to(submission)}"
            sb.filesystem.make_directory(str(Path(remote).parent))
            sb.filesystem.copy_from_local(path, remote)


def evaluate_submission(cfg: Config, app: modal.App, submission: Path, out_dir: Path, quiet: bool = False) -> dict:
    """Returns eval.json contents; `sandbox_seconds` is the eval sandbox's billed lifetime (for cost)."""
    log = (lambda *a: None) if quiet else print
    out_dir.mkdir(parents=True, exist_ok=True)
    processed = cfg.data.processed_dir
    result: dict = {"passed": False, "sandbox_seconds": 0.0}

    file_errors = check_files(submission)
    if file_errors:
        result["file_errors"] = file_errors
        (out_dir / "eval.json").write_text(json.dumps(result, indent=2))
        log(f"evaluation FAILED before running: {file_errors}")
        return result

    requirements = [l.split("#", 1)[0].strip() for l in (submission / "requirements.txt").read_text().splitlines()]
    requirements = [r for r in requirements if r]
    log(f"evaluation: building image (extra requirements: {requirements or 'none'}), starting network-blocked sandbox ...")
    e = cfg.evaluation
    sb = modal.Sandbox.create(
        app=app, image=eval_image(requirements, train_dir=processed / "train", test_dir=processed / "test_features"),
        cpu=e.cpu, memory=e.memory_mb, timeout=e.timeout_s, workdir=WORKDIR, block_network=True,
    )
    started = time.time()
    try:
        _upload_submission(sb, submission)
        probe = sb.exec("bash", "-c", NETWORK_PROBE)
        result["network_probe"] = probe.stdout.read().strip()
        probe.wait()
        proc = sb.exec(
            "python", f"{HARNESS_DIR}/run_submission.py", "--submission", f"{WORKDIR}/submission",
            "--train-dir", TRAIN_DATA_DIR, "--test-dir", TEST_DATA_DIR, "--work-dir", "/tmp/eval",
            "--train-timeout", str(e.train_timeout_s), "--predict-timeout", str(e.predict_timeout_s),
        )
        proc.stdout.read()
        proc.wait()
        result.update(json.loads(sb.filesystem.read_text("/tmp/eval/result.json")))
        if result["passed"]:
            (out_dir / "preds.csv").write_bytes(sb.filesystem.read_bytes("/tmp/eval/preds.csv"))
    finally:
        sb.terminate()
        result["sandbox_seconds"] = round(time.time() - started, 1)

    result["sandbox_id"] = sb.object_id
    result["network_blocked"] = result.get("network_probe") == "network blocked"
    if result["passed"]:
        result["test_scores"] = score(pd.read_csv(out_dir / "preds.csv"), pd.read_csv(processed / "test_labels.csv"))
    result["passed"] = bool(result["passed"]) and result["network_blocked"]

    log(f"network probe: {result.get('network_probe')}")
    for step in result.get("steps", []):
        log(f"{step['step']}: {step['status']} in {step['seconds']}s (limit {step['timeout_s']}s)")
        if step["status"] != "ok":
            log(f"--- stderr tail ---\n{step['stderr_tail']}")
    for err in result.get("prediction_errors", []):
        log(f"PREDICTION ERROR: {err}")
    if result.get("test_scores"):
        log(f"TEST SCORES: {json.dumps(result['test_scores'])}")
    (out_dir / "eval.json").write_text(json.dumps(result, indent=2))
    log(f"evaluation {'PASSED' if result['passed'] else 'FAILED'} -> {out_dir / 'eval.json'}")
    return result


def _exit_on_sigterm(signum, frame):
    raise SystemExit(143)  # run the `finally` blocks so sandboxes get terminated


def main() -> None:
    signal.signal(signal.SIGTERM, _exit_on_sigterm)
    cfg = load_config()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("submission", type=Path)
    parser.add_argument("--out", type=Path, help="defaults to the submission's parent directory")
    args = parser.parse_args()
    submission = args.submission.resolve()
    app = modal.App.lookup(cfg.modal.app_name, create_if_missing=True)
    evaluate_submission(cfg, app, submission, (args.out or submission.parent).resolve())


if __name__ == "__main__":
    main()
