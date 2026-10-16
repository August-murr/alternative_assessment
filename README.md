# alternative_assessment

An autonomous Claude Code agent runs in a Modal CPU sandbox and builds a **script** that trains a late-delivery classifier on the
[Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
The script, not a model, is the submission. It is re-run from scratch in a network-blocked sandbox and scored on a held-out later time period. That makes the model reproducible and the training data auditable.

```
data_prep/   download → explore → prepare (leakage removal, temporal split, ID re-keying)
tasks/       one directory per task: PROMPT.md (what the agent is told), task.yaml, extra files
harness/     runs a submission (train.py → predict.py → format check); shared by the agent and the evaluator
sandbox/     image definitions, agent runner, network-blocked evaluator, trace printer, run summary
```

## Setup

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env    # then paste your tokens
```

`.env` holds:
- `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET`: from https://modal.com/settings/tokens.
- `CLAUDE_CODE_OAUTH_TOKEN`: from running `claude setup-token`. You can set `ANTHROPIC_API_KEY` instead.
- `DATA_SALT`: a secret salt used to re-key IDs.

All other settings live in `config.yaml`: sandbox CPU, memory and timeout, model, effort, turn and dollar caps, tools, and evaluator limits.

## 1. Dataset

```bash
.venv/bin/python -m data_prep.download && .venv/bin/python -m data_prep.explore && .venv/bin/python -m data_prep.prepare
```

| Path | Contents | Who sees it |
|---|---|---|
| `data/processed/train/` | 8 feature tables + `train_labels.csv` | agent sandbox (`/data/train`) |
| `data/processed/test_features/` | same 8 tables, no labels | evaluator sandbox only |
| `data/processed/test_labels.csv` | `order_id, is_late` | **never enters a sandbox**; scoring happens locally |

- Prediction time is the moment of purchase. The split is temporal: the last 20% of orders are the test set.
- Post-purchase columns and the reviews table are removed, and IDs are re-keyed with a secret salt.
- The evidence for each removal is in [data_prep/LEAKAGE.md](data_prep/LEAKAGE.md). [tasks/olist/DATA.md](tasks/olist/DATA.md) is the agent-facing description, and it deliberately contains no test-set statistics.

## 2. Run the agent

```bash
.venv/bin/python -m sandbox.run_agent                       # task from config.yaml (tasks/olist)
.venv/bin/python -m sandbox.run_agent --task tasks/hello    # trivial smoke test
.venv/bin/python -m sandbox.run_agent --effort high --max-turns 200 --max-budget-usd 20
```

1. The agent sandbox starts with the training data at `/data/train`, plus `DATA.md`, `TASK.md` and the `validate-submission` command.
2. Claude Code runs headless (`claude -p`) on the task prompt, and every event streams live to the terminal.
3. When it exits, `/workspace/submission/` and Claude Code's session log are copied back.
4. **Evaluation:** a new sandbox with `block_network=True` ([Modal docs](https://modal.com/docs/guide/sandbox-networking)) is started. Its image contains the submission's `requirements.txt` (installed at build time), the training data and the test features.
   - It first confirms outbound network is blocked.
   - It then runs `train.py` and `predict.py` under time limits and checks `preds.csv`.
   - `preds.csv` is scored locally: PR-AUC is primary, ROC-AUC and Brier score are also reported.
5. A one-page `SUMMARY.md` is written.

### The submission contract
- `python train.py --data-dir DIR --model-dir DIR`
- `python predict.py --model-dir DIR --data-dir DIR --output FILE`, which writes `order_id,p_late` for every order
- `requirements.txt` (plain pinned specs only) and `REPORT.md`

### How the agent confirms its submission: `validate-submission`
- It holds out the last 20% of the agent's training orders and runs the submission through the **same harness code** the evaluator uses: same commands, same time limits, same format checks.
- It then prints scores on that pseudo test set.
- The prompt requires it to pass before the agent finishes.

### Agent restrictions (deliberate)
- **Limited tool set.** The agent gets only `Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch` (`agent.tools` in `config.yaml`, passed as `--tools` and `--allowedTools`), and `--disable-slash-commands` removes skills.
  - Claude Code otherwise exposes about 25 tools, including scheduling (`CronCreate`, `ScheduleWakeup`), remote triggers, push notifications, subagents and worktrees.
  - None of those are needed for an ML task, and some act outside the sandbox or on the account. We want the agent's actions to be easy to audit.
- **Credentials are hidden from the agent's shell.** `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` removes the Claude token from every Bash subprocess, and Claude Code keeps it for its own API calls.
  - It also runs shell commands in Claude Code's own sandbox (bubblewrap, so `bubblewrap` and `socat` are installed in the image). Commands can't read the token through `/proc` either; this was verified in Modal.
  - Side effect: Claude Code drops `--dangerously-skip-permissions`, which is why the tools are pre-approved with `--allowedTools`.
- **No telemetry:** `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`.
- **Internet stays on** in the agent sandbox, so the agent can `pip install` and search. The submission can't depend on the network because evaluation is offline.

### Watching a run
- **Live:** `tail -f runs/live.log`, if you redirect output there, or the terminal you started it in. The Modal dashboard URL is printed at the start.
- **Replay:** `python -m sandbox.trace runs/<id>/transcript.jsonl [--full]`.
- **Re-run parts:** `python -m sandbox.evaluate runs/<id>` and `python -m sandbox.summary runs/<id>`.

```
runs/<timestamp>-<task>/
  prompt.md          the exact prompt sent
  transcript.jsonl   raw stream-json events
  session/           Claude Code's native session log
  submission/        train.py, predict.py, requirements.txt, REPORT.md, ...
  run.json           config snapshot, turns, cost, sandbox id
  eval.json          network check, step timings, format errors, test scores
  preds.csv          the submission's test predictions
  SUMMARY.md         one-page overview
```

## Limits that control how much the agent does
- `agent.effort`: `low` to `max`.
- `agent.max_turns` and `agent.max_budget_usd`: `null` means unlimited.
- `modal.timeout_s`: the hard wall-clock limit for the agent sandbox.
- `BASH_MAX_TIMEOUT_MS`: the longest a single shell command may run.
- `evaluation.train_timeout_s` and `evaluation.predict_timeout_s`: the limits the agent is told about and the evaluator enforces.
