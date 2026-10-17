You are running autonomously inside an isolated Linux sandbox. Nobody will answer questions, so make your own decisions.

# Task: predict late deliveries

Build a model that predicts, **at the moment an order is placed**, the probability that it will be delivered later than the date promised to the customer.

Your deliverable is not a trained model but **code that trains the model**. We will run your code from scratch on the full training data, then use it to predict a later, held-out period of orders you never see.

## How this run works: 10 short iterations
You'll work in **10 iterations**. After each one, your submission is saved as a checkpoint and verified before you get the next instruction. We want to see **gradual, step-by-step progress**, so:
- **Iteration 1 (this one):** build a deliberately **minimal baseline**: a handful of obvious features and a default model. Don't optimize. Also write `PLAN.md`: a roadmap of 9 small improvement steps, one per remaining iteration, in the order you'd try them.
- **Each later iteration:** make exactly **one** focused change (one feature group, one modeling change, or one tuning step). Keep iterations short: a few minutes and a few tool calls. Don't spend an iteration on several changes.
- Measure each change with `validate-submission` and report the effect honestly, including when it made things worse.

## Environment
- Training data: `/data/train/`. Read `/workspace/DATA.md` first: it describes every table, the target, and the prediction-time rule.
- This task description is also saved at `/workspace/TASK.md`.
- Preinstalled Python 3.12 packages: numpy==2.5.4, pandas==3.0.6, pyarrow==26.0.0, scipy==1.18.1, scikit-learn==1.9.1, lightgbm==4.7.0, xgboost==3.4.1, catboost==1.2.10, matplotlib==3.11.2, optuna==5.0.0. You may `pip install` others; list them in `requirements.txt`.
- This sandbox has 4 CPUs and 8 GB RAM and internet access.

## Rules
1. **Only use information available at purchase time** as model inputs (see `DATA.md`). The test data won't contain `train_labels.csv`.
2. **Each order's features may only use that order and data from before its purchase time.** Never compute features from other orders in the file being predicted (e.g. counts of orders on the same day or week), because at prediction time the rest of that batch hasn't happened yet. Aggregates learned from the training data (e.g. a seller's historical late rate) are fine.
3. Use only the data in `/data/train/`. Don't download or use any other copy of the Olist dataset.
4. Your code must learn from the data it's given. Don't hardcode IDs, labels or other data into the submission.

## Submission: `/workspace/submission/`
| file | what it must do |
|---|---|
| `train.py` | `python train.py --data-dir DIR --model-dir DIR`: read the training tables from `--data-dir` (same layout as `/data/train/`, including `train_labels.csv`), train, and save everything needed for prediction into `--model-dir`. |
| `predict.py` | `python predict.py --model-dir DIR --data-dir DIR --output FILE`: load the model from `--model-dir`, read the feature tables from `--data-dir` (same layout but **without** `train_labels.csv`), and write a CSV to `--output` with exactly the columns `order_id,p_late`: one row for every order in `orders.csv`, with `p_late` in [0, 1]. |
| `requirements.txt` | Extra packages you used beyond the preinstalled ones, one plain pinned spec per line (e.g. `somepkg==1.2.3`). May be empty. No URLs or pip options. |
| `REPORT.md` | A running report: approach, features and why they're legitimate at purchase time, validation results per iteration, known weaknesses. Update it every iteration. |
| `CHECKPOINT.md` | **Overwrite every iteration** with exactly this structure:<br>`# Checkpoint <n>`<br>`Change: <one line>`<br>`Why: <one or two sentences>`<br>`Validation PR-AUC: <before> -> <after>`<br>`Decision: kept / reverted, and why` |
| `PLAN.md` | Your roadmap of small steps. Update it when your plans change. |

`train.py` and `predict.py` may import other `.py` files in the submission folder. They must not depend on anything else in `/workspace`.

## How you'll be evaluated
- We copy `/workspace/submission/` into a fresh sandbox with the same preinstalled packages plus your `requirements.txt`, with **no network access**, 4 CPUs and 8 GB RAM.
- `train.py` runs on the full training data with a **20-minute** limit. `predict.py` runs on the held-out test orders with a **5-minute** limit.
- **Primary metric: PR-AUC (average precision) of `p_late` on the test orders.** We also report ROC-AUC and the Brier score.
- We read your code to check that no post-purchase information or hardcoded data is used.

## Check your submission: `validate-submission`
Run `validate-submission` in the shell. It holds out the last 20% of your training orders as a pseudo test set and runs your submission exactly as the evaluator does: same commands, same time limits, network disabled where possible. Then it checks the output format and prints scores on that pseudo test set. **The submission must pass it at the end of every iteration.** Its scores come from data you have, so treat them as a guide, not the final score.

## This iteration is done when
The baseline passes `validate-submission`, and `REPORT.md`, `CHECKPOINT.md` (`# Checkpoint 1`, with `Validation PR-AUC: none -> <score>`) and `PLAN.md` are written. Then stop and wait for the next instruction.
