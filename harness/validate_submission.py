"""validate-submission: dry-run the official evaluation on a split of the training data.

Takes the last 20% of training orders (by purchase time) as a pseudo test set, then runs
/workspace/submission exactly as the evaluator will:
  python train.py   --data-dir <pseudo-train> --model-dir <dir>
  python predict.py --model-dir <dir> --data-dir <pseudo-test> --output <file>
under the same time limits, checks the output format, and scores the predictions.

The score is on data you already have, so it's only a sanity check, not the final test score.

    validate-submission [--submission /workspace/submission] [--holdout-fraction 0.2]
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

sys.path.insert(0, str(Path(__file__).parent))
from run_submission import run_submission  # noqa: E402

TRAIN_DIR = Path(os.environ.get("TRAIN_DATA_DIR", "/data/train"))
WORK = Path("/tmp/validate-submission")


def make_pseudo_split(train_dir: Path, out: Path, holdout_fraction: float) -> pd.DataFrame:
    """Split the training data by purchase time into pseudo-train (with labels) and pseudo-test (without)."""
    orders = pd.read_csv(train_dir / "orders.csv", parse_dates=["order_purchase_timestamp"])
    orders = orders.sort_values(["order_purchase_timestamp", "order_id"], kind="stable")
    boundary = orders["order_purchase_timestamp"].iloc[int(len(orders) * (1 - holdout_fraction))]
    test_ids = set(orders.loc[orders["order_purchase_timestamp"] >= boundary, "order_id"])
    test_customers = set(orders.loc[orders["order_id"].isin(test_ids), "customer_id"])

    p_train, p_test = out / "train", out / "test"
    p_train.mkdir(parents=True)
    p_test.mkdir(parents=True)
    labels = pd.read_csv(train_dir / "train_labels.csv")
    for csv in sorted(train_dir.glob("*.csv")):
        df = pd.read_csv(csv)
        if "order_id" in df.columns:
            in_test = df["order_id"].isin(test_ids)
        elif csv.name == "customers.csv":
            in_test = df["customer_id"].isin(test_customers)
        else:  # lookup tables (products, sellers, geolocation, categories): both sides get all rows
            df.to_csv(p_train / csv.name, index=False)
            df.to_csv(p_test / csv.name, index=False)
            continue
        df[~in_test].to_csv(p_train / csv.name, index=False)
        if csv.name != "train_labels.csv":
            df[in_test].to_csv(p_test / csv.name, index=False)
    return labels[labels["order_id"].isin(test_ids)][["order_id", "is_late"]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--submission", type=Path, default=Path("/workspace/submission"))
    parser.add_argument("--holdout-fraction", type=float, default=0.2)
    args = parser.parse_args()

    if WORK.exists():
        shutil.rmtree(WORK)
    print(f"building pseudo split from {TRAIN_DIR} (last {args.holdout_fraction:.0%} of orders held out) ...")
    test_labels = make_pseudo_split(TRAIN_DIR, WORK / "data", args.holdout_fraction)

    train_timeout = int(os.environ.get("EVAL_TRAIN_TIMEOUT_S", 1200))
    predict_timeout = int(os.environ.get("EVAL_PREDICT_TIMEOUT_S", 300))
    print(f"running submission (train limit {train_timeout}s, predict limit {predict_timeout}s) ...")
    result = run_submission(args.submission, WORK / "data" / "train", WORK / "data" / "test", WORK / "run",
                            train_timeout, predict_timeout, no_network=True)

    print("\n=== validate-submission ===")
    for err in result["file_errors"]:
        print(f"FILE ERROR: {err}")
    for step in result["steps"]:
        print(f"{step['step']}: {step['status']} in {step['seconds']}s (limit {step['timeout_s']}s)")
        if step["status"] != "ok":
            print(f"--- {step['step']} stderr (tail) ---\n{step['stderr_tail']}")
    for err in result["prediction_errors"]:
        print(f"PREDICTION ERROR: {err}")
    if not result["network_isolated_by_harness"]:
        print("note: network could not be disabled here; the real evaluation has NO network access")

    if result["passed"]:
        preds = pd.read_csv(WORK / "run" / "preds.csv").merge(test_labels, on="order_id")
        y, p = preds["is_late"], preds["p_late"]
        scores = {
            "pr_auc": round(average_precision_score(y, p), 4),
            "roc_auc": round(roc_auc_score(y, p), 4),
            "brier": round(brier_score_loss(y, p), 4),
            "positive_rate": round(float(y.mean()), 4),
        }
        result["pseudo_test_scores"] = scores
        print(f"scores on pseudo test ({len(preds)} orders): {json.dumps(scores)}")
        print("PASSED: the submission format is valid. (These scores are not the final test score.)")
    else:
        print("FAILED: fix the errors above and run validate-submission again.")
    (WORK / "summary.json").write_text(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
