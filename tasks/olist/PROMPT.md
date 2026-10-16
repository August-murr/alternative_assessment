You are running autonomously inside an isolated Linux sandbox. Nobody will answer questions, so make your own decisions and carry the task through to a finished submission.

# Task: predict late deliveries

Build a model that predicts, **at the moment an order is placed**, the probability that it will be delivered later than the date promised to the customer.

Your deliverable is not a trained model but **code that trains the model**. We will run your code from scratch on the full training data, then use it to predict a later, held-out period of orders you never see.

## Environment
- Training data: `${train_data_dir}/`. Read `/workspace/DATA.md` first: it describes every table, the target, and the prediction-time rule.
- This task description is also saved at `/workspace/TASK.md`.
- Preinstalled Python 3.12 packages: ${ml_packages}. You may `pip install` others; list them in `requirements.txt`.
- This sandbox has ${agent_cpu} CPUs and ${agent_memory_gb} GB RAM. It has internet access. It is shut down after ${agent_timeout_min} minutes, so keep your submission in a working state as you go.

## Rules
1. **Only use information available at purchase time** as model inputs (see `DATA.md`). The test data won't contain `train_labels.csv`.
2. Use only the data in `${train_data_dir}/`. Don't download or use any other copy of the Olist dataset.
3. Your code must learn from the data it's given. Don't hardcode IDs, labels or other data into the submission.

## Submission: `/workspace/submission/`
| file | what it must do |
|---|---|
| `train.py` | `python train.py --data-dir DIR --model-dir DIR`: read the training tables from `--data-dir` (same layout as `${train_data_dir}/`, including `train_labels.csv`), train, and save everything needed for prediction into `--model-dir`. |
| `predict.py` | `python predict.py --model-dir DIR --data-dir DIR --output FILE`: load the model from `--model-dir`, read the feature tables from `--data-dir` (same layout but **without** `train_labels.csv`), and write a CSV to `--output` with exactly the columns `order_id,p_late`: one row for every order in `orders.csv`, with `p_late` in [0, 1]. |
| `requirements.txt` | Extra packages you used beyond the preinstalled ones, one plain pinned spec per line (e.g. `somepkg==1.2.3`). May be empty. No URLs or pip options. |
| `REPORT.md` | A short report: your approach, the features and why they're legitimate at purchase time, how you validated, the validation results, and known weaknesses. |

`train.py` and `predict.py` may import other `.py` files you put in the submission folder. They must not depend on anything else in `/workspace`.

## How you'll be evaluated
- We copy `/workspace/submission/` into a fresh sandbox with the same preinstalled packages plus your `requirements.txt`, with **no network access**, ${eval_cpu} CPUs and ${eval_memory_gb} GB RAM.
- `train.py` runs on the full training data with a **${train_timeout_min}-minute** limit. `predict.py` runs on the held-out test orders with a **${predict_timeout_min}-minute** limit.
- **Primary metric: PR-AUC (average precision) of `p_late` on the test orders.** We also report ROC-AUC and the Brier score.
- We read your code to check that no post-purchase information or hardcoded data is used.

## Check your submission: `validate-submission`
Run `validate-submission` in the shell at any time. It holds out the last 20% of your training orders as a pseudo test set and runs your submission exactly as the evaluator does: same commands, same time limits, network disabled where possible. Then it checks the output format and prints scores on that pseudo test set. **Your submission must pass it before you finish.** Its scores come from data you have, so treat them as a sanity check, not the final score.

## Done when
`/workspace/submission/` contains all four files and `validate-submission` passes. Then stop.
