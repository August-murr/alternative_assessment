"""Run a submission end to end: train.py, then predict.py, then check the predictions file.

Used in two places with identical rules:
  - inside the agent sandbox, by `validate-submission` (on a split of the training data)
  - inside the network-blocked evaluator sandbox (on the real held-out test features)

    python run_submission.py --submission DIR --train-dir DIR --test-dir DIR --work-dir DIR \
        [--train-timeout S] [--predict-timeout S] [--no-network]

Writes <work-dir>/result.json and <work-dir>/preds.csv. Exit code 0 only if everything passed.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

REQUIRED_FILES = ["train.py", "predict.py", "requirements.txt", "REPORT.md"]
# One plain requirement per line, e.g. "lightgbm==4.7.0". No pip options, URLs, or VCS links.
REQUIREMENT_LINE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*(\[[A-Za-z0-9,._\-]+\])?\s*((==|>=|<=|~=|!=|>|<)\s*[A-Za-z0-9.*+!\-]+\s*,?\s*)*$")
TAIL = 4000


def check_files(submission: Path) -> list[str]:
    errors = [f"missing {name}" for name in REQUIRED_FILES if not (submission / name).is_file()]
    req = submission / "requirements.txt"
    if req.is_file():
        for n, raw in enumerate(req.read_text().splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if line and not REQUIREMENT_LINE.match(line):
                errors.append(f"requirements.txt line {n} is not a plain package spec: {raw!r}")
    return errors


def network_isolation_prefix() -> list[str]:
    """Best-effort: run in a fresh network namespace with no interfaces, if the kernel allows it."""
    try:
        ok = subprocess.run(["unshare", "-rn", "true"], capture_output=True, timeout=10).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        ok = False
    return ["unshare", "-rn"] if ok else []


def run_step(name: str, cmd: list[str], cwd: Path, timeout: int) -> dict:
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        status = "ok" if proc.returncode == 0 else "failed"
        out, err, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        status, code = "timeout", None
        out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = (e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    return {
        "step": name, "status": status, "exit_code": code, "seconds": round(time.time() - started, 1),
        "timeout_s": timeout, "stdout_tail": out[-TAIL:], "stderr_tail": err[-TAIL:],
    }


def check_predictions(preds_path: Path, test_dir: Path) -> list[str]:
    if not preds_path.is_file():
        return ["predict.py did not write the output file"]
    try:
        preds = pd.read_csv(preds_path)
    except Exception as e:  # noqa: BLE001
        return [f"output is not a readable CSV: {e}"]
    errors = []
    if list(preds.columns) != ["order_id", "p_late"]:
        errors.append(f"columns must be exactly ['order_id', 'p_late'], got {list(preds.columns)}")
        return errors
    expected = set(pd.read_csv(test_dir / "orders.csv", usecols=["order_id"])["order_id"])
    got = preds["order_id"]
    if got.duplicated().any():
        errors.append(f"{int(got.duplicated().sum())} duplicate order_ids")
    missing, extra = expected - set(got), set(got) - expected
    if missing:
        errors.append(f"{len(missing)} order_ids from orders.csv are missing")
    if extra:
        errors.append(f"{len(extra)} order_ids not in orders.csv")
    p = pd.to_numeric(preds["p_late"], errors="coerce")
    if p.isna().any():
        errors.append(f"{int(p.isna().sum())} p_late values are missing or non-numeric")
    if ((p < 0) | (p > 1)).any():
        errors.append("p_late values must be within [0, 1]")
    return errors


def run_submission(submission: Path, train_dir: Path, test_dir: Path, work_dir: Path,
                   train_timeout: int, predict_timeout: int, no_network: bool = False) -> dict:
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)
    sub, model_dir, preds = work_dir / "submission", work_dir / "model", work_dir / "preds.csv"
    shutil.copytree(submission, sub, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    model_dir.mkdir()

    result = {"passed": False, "file_errors": check_files(sub), "steps": [], "prediction_errors": []}
    prefix = network_isolation_prefix() if no_network else []
    result["network_isolated_by_harness"] = bool(prefix)
    if not result["file_errors"]:
        py = sys.executable
        train = run_step("train", prefix + [py, "train.py", "--data-dir", str(train_dir), "--model-dir", str(model_dir)],
                         sub, train_timeout)
        result["steps"].append(train)
        if train["status"] == "ok":
            predict = run_step("predict", prefix + [py, "predict.py", "--model-dir", str(model_dir),
                                                    "--data-dir", str(test_dir), "--output", str(preds)],
                               sub, predict_timeout)
            result["steps"].append(predict)
            if predict["status"] == "ok":
                result["prediction_errors"] = check_predictions(preds, test_dir)
                result["passed"] = not result["prediction_errors"]
    (work_dir / "result.json").write_text(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--train-dir", type=Path, required=True)
    parser.add_argument("--test-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--train-timeout", type=int, default=1200)
    parser.add_argument("--predict-timeout", type=int, default=300)
    parser.add_argument("--no-network", action="store_true")
    args = parser.parse_args()
    result = run_submission(args.submission, args.train_dir, args.test_dir, args.work_dir,
                            args.train_timeout, args.predict_timeout, args.no_network)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
