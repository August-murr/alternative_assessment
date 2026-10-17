# Documentation

How the pipeline works, how to run it, and why it's built the way it is. For results, see [REPORT.md](REPORT.md).

## Contents
1. [Overview](#1-overview)
2. [Repository layout](#2-repository-layout)
3. [Setup](#3-setup)
4. [Data preparation and leakage controls](#4-data-preparation-and-leakage-controls)
5. [The agent run](#5-the-agent-run)
6. [Checkpoints and verification](#6-checkpoints-and-verification)
7. [Offline evaluation](#7-offline-evaluation)
8. [Cost accounting](#8-cost-accounting)
9. [Agent restrictions](#9-agent-restrictions)
10. [Observing a run](#10-observing-a-run)
11. [Configuration reference](#11-configuration-reference)

## 1. Overview

```
            ┌──────────────── agent sandbox (Modal, internet on) ────────────────┐
 prompt ──▶ │ Claude Code (headless) ──writes──▶ /workspace/submission/            │
            │   tools: Bash Read Write Edit Glob Grep WebSearch WebFetch           │
            │   data:  /data/train (train split only)    validate-submission      │
            └──────────────────────────────┬──────────────────────────────────────┘
                     each iteration: verify ▼ snapshot → checkpoints/cp_k/
            ┌──────────── eval sandbox (Modal, block_network=True) ──────────────┐
            │ pip install requirements.txt (at image build) → train.py → predict.py│
            │ data: /data/train + /data/test_features (no labels)                  │
            └──────────────────────────────┬──────────────────────────────────────┘
                                 preds.csv ▼ scored locally against test_labels.csv
```

- The agent is evaluated on **code that produces a model**, not on a model. Every checkpoint is retrained from scratch in a separate offline sandbox.
- Test labels never enter any sandbox.
- The agent never sees test scores.

## 2. Repository layout

```
README.md            abstract
docs/                DOCUMENTATION.md (this file), REPORT.md (results), LEAKAGE.md (data decisions)
results/<run>/       committed outputs of the reported run(s)
tasks/olist/         what the agent is told: PROMPT.md, ITERATE.md, FIX.md, DATA.md
pipeline/
  run.py             orchestrator: sandbox, iterations, verification, checkpoints, costs
  evaluate.py        network-blocked evaluator + scoring
  report.py          checkpoint reports, progress table, charts, summary, --publish
  costs.py           API + Modal cost model
  config.py          config.yaml + .env loading
  data/              download.py, explore.py, prepare.py
  harness/           run_submission.py, validate_submission.py (copied into both sandboxes)
  sandbox/           image.py (container images), trace.py (live trace printer)
config.yaml          all settings
```

## 3. Setup

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env   # fill in the values below
```

| `.env` key | Purpose |
|---|---|
| `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` | Modal account (https://modal.com/settings/tokens) |
| `CLAUDE_CODE_OAUTH_TOKEN` | from `claude setup-token`; alternatively set `ANTHROPIC_API_KEY` |
| `DATA_SALT` | secret salt for re-keying dataset IDs |

```bash
.venv/bin/python -m pipeline.data.download    # Kaggle → data/raw (anonymous download works)
.venv/bin/python -m pipeline.data.explore     # prints the evidence behind the leakage decisions
.venv/bin/python -m pipeline.data.prepare     # → data/processed/{train, test_features, test_labels.csv}
.venv/bin/python -u -m pipeline.run --iterations 3 > runs/live.log 2>&1   # then: tail -f runs/live.log
.venv/bin/python -m pipeline.report runs/<id> --publish                     # copy results to results/
```

## 4. Data preparation and leakage controls

Full evidence is in [LEAKAGE.md](LEAKAGE.md). In short:

- **Prediction time is the moment of purchase.** The label is `is_late = date(delivered) > estimated delivery date`, on delivered orders only.
- **Post-purchase information is removed:**
  - the reviews table (late orders score 2.3 vs 4.2)
  - order status
  - payment approval time
  - carrier and customer delivery dates, which are kept only in `train_labels.csv` for training
  - the seller shipping deadline, which turned out to be approval time plus N days
- **Temporal split:** the last 20% of orders by purchase time are the test set (train 2016-09 → 2018-04-16, test → 2018-07-04).
- **Right-censoring guard:** orders purchased after 2018-07-05 are dropped. Near the data snapshot, late orders hadn't been delivered yet, which biased the tail toward on-time.
- **Salted ID re-keying:** a submission can't embed a lookup from public Kaggle IDs to labels.
- The agent sees `train/` and [tasks/olist/DATA.md](../tasks/olist/DATA.md). `DATA.md` contains no test-set statistics.
- The prompt adds rules that the data can't enforce:
  - only use purchase-time information
  - don't compute features from other orders in the file being predicted (a leak an early run actually produced)
  - don't use other copies of the dataset
  - don't hardcode data

## 5. The agent run

`pipeline/run.py` starts **one** Modal sandbox and **one** Claude Code session per run. Then, for each iteration:

1. It sends a prompt:
   - [PROMPT.md](../tasks/olist/PROMPT.md) for iteration 1: the full task and the iteration protocol
   - [ITERATE.md](../tasks/olist/ITERATE.md) for later iterations, as `claude -p ... --resume <session>` so the agent keeps its context
2. Claude Code runs headless: `claude -p --output-format stream-json --verbose --model ... --effort ...`, with the restrictions in §9.

**Prompting for gradual progress.** The task saturates quickly, so the prompt asks for:
- a deliberately minimal baseline in iteration 1, plus a written roadmap (`PLAN.md`)
- exactly one small change per later iteration, measured with `validate-submission`
- honest reporting of regressions

This produces a sequence of checkpoints instead of a single near-final result.

**Submission contract** (enforced by the harness):

| file | contract |
|---|---|
| `train.py` | `python train.py --data-dir DIR --model-dir DIR` |
| `predict.py` | `python predict.py --model-dir DIR --data-dir DIR --output FILE` → CSV `order_id,p_late` for every order |
| `requirements.txt` | extra packages, plain pinned specs only (no URLs or pip options) |
| `REPORT.md`, `CHECKPOINT.md`, `PLAN.md` | running report, per-iteration note (fixed format), roadmap |

## 6. Checkpoints and verification

After each iteration the orchestrator, not the agent, verifies the checkpoint:

1. **It runs `validate-submission` in the agent sandbox, outside Claude.**
   - It holds out the last 20% of the training orders as a pseudo test set.
   - It runs the submission through [pipeline/harness/run_submission.py](../pipeline/harness/run_submission.py), the same code the evaluator uses: same commands, time limits and format checks.
   - It records the pseudo-test scores, which are the "validation" numbers.
2. **If verification fails,** [FIX.md](../tasks/olist/FIX.md) is sent with the error, up to `max_fix_attempts` times. If it still fails, the checkpoint is marked failed and the submission is rolled back to the last good checkpoint.
3. **It snapshots** `/workspace/submission` to `checkpoints/cp_<k>/submission/`, with a `diff.patch` against the previous good checkpoint.
4. **It evaluates the checkpoint offline** (§7) in a background thread while the next iteration runs.

The agent can run `validate-submission` itself at any time, and the prompt requires it to pass before stopping.

## 7. Offline evaluation

[pipeline/evaluate.py](../pipeline/evaluate.py) runs each checkpoint in a fresh sandbox created with `block_network=True`, which per [Modal's docs](https://modal.com/docs/guide/sandbox-networking) drops all outbound traffic.

1. The image is the shared ML base plus the checkpoint's `requirements.txt`, installed at **build** time while the network is available, plus `train/` and `test_features/`.
2. A probe confirms that outbound requests fail. A checkpoint only passes if they do.
3. `train.py` runs on the full training data within `train_timeout_s`, then `predict.py` runs on the test features within `predict_timeout_s`.
4. `preds.csv` is checked (all orders present, probabilities between 0 and 1), copied out, and **scored locally**:
   - **PR-AUC** (primary)
   - ROC-AUC
   - Brier score
   - the positive rate (the PR-AUC of a random model) is reported alongside

## 8. Cost accounting

[pipeline/costs.py](../pipeline/costs.py). Each checkpoint's cost is **Claude API + Modal agent sandbox + Modal eval sandbox**.

- **Claude API:** every `claude -p` call ends with a `result` event whose `total_cost_usd` is Claude Code's estimate at API list prices.
  - When a call resumes a session, that figure is cumulative for the conversation, so a checkpoint's API cost is the difference between consecutive totals. Fix attempts count toward their checkpoint.
  - With a subscription token this is the API-equivalent value, not money billed.
- **Modal:** there's no per-sandbox cost API on individual plans; the billing API requires a Team plan and reports hourly. Modal cost is therefore an estimate: `seconds × (CPU cores × $0.00003942 + GiB × $0.00000667)`, Modal's published Sandbox rates, set in `config.yaml` under `pricing`.
  - Agent sandbox time is split by iteration. Startup counts toward checkpoint 1 and teardown toward the last.
  - Each eval sandbox's lifetime counts toward its checkpoint.
  - Image build time isn't counted (images are cached).
- **Outputs:**
  - `progress.csv`: per-checkpoint scores and cost components
  - `cost_curve.png`: two aligned panels, score per checkpoint on top and cumulative cost stacked by source (Claude API, Modal agent sandbox, Modal eval sandbox) below

## 9. Agent restrictions

These are deliberate, so the agent's actions stay auditable and contained:

- **Limited tools:** only `Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch`, via `--tools` and `--allowedTools`; `--disable-slash-commands` turns off skills.
  - Claude Code otherwise exposes about 25 tools, including scheduling (`CronCreate`, `ScheduleWakeup`), remote triggers, push notifications, subagents and worktrees.
  - An ML task needs none of these, and some act outside the sandbox or on the account.
- **Credentials hidden from shell commands:** `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` removes the Claude token from every Bash subprocess, while Claude Code keeps it for API calls.
  - Shell commands also run in Claude Code's bubblewrap sandbox, so they can't read the token through `/proc`. Verified in Modal: 0 credential variables were visible.
  - This needs `bubblewrap` and `socat` in the image. It also forces the permission mode back to default, which is why tools are pre-approved with `--allowedTools`.
- **No telemetry:** `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`.
- **Internet stays on** in the agent sandbox, for `pip install` and search. The submission can't depend on it, because evaluation is offline.
- **Root:** the sandbox runs as root, so `IS_SANDBOX=1` is set. The Modal container is the isolation boundary.

## 10. Observing a run

- **Live:** `tail -f runs/live.log`. It shows the agent's text, tool calls with abbreviated output, iteration banners, verification results and cost per checkpoint. The Modal dashboard URL is printed at the start.
- **Replay:** `python -m pipeline.sandbox.trace runs/<id>/transcript.jsonl [--full]`.
- **Raw records:**
  - `transcript.jsonl`: every stream-json event
  - `session/`: Claude Code's native session log
- **Per checkpoint:** `checkpoints/cp_<k>/` contains:
  - `CHECKPOINT_REPORT.md` (scores and deltas, cost, the agent's note)
  - `checkpoint.json`
  - `diff.patch`
  - `eval.json`
  - `submission/`
- **Run level:**
  - `SUMMARY.md`
  - `progress.csv`
  - charts
  - `run.json` (a full config snapshot)

## 11. Configuration reference

`config.yaml`:

| key | meaning |
|---|---|
| `agent.iterations` | checkpoints per run (1 = one-shot) |
| `agent.iteration_timeout_s` | limit for one `claude -p` call |
| `agent.max_fix_attempts` | extra calls when verification fails |
| `agent.model`, `agent.effort` | model and effort level (`low` … `max`) |
| `agent.max_turns`, `agent.max_budget_usd` | per-call caps (`null` = none) |
| `agent.tools`, `agent.disable_slash_commands`, `agent.env` | restrictions (§9) and the agent's environment, including `BASH_MAX_TIMEOUT_MS` |
| `modal.cpu`, `modal.memory_mb`, `modal.timeout_s` | agent sandbox resources and wall-clock limit |
| `evaluation.*` | eval sandbox resources and the train/predict time limits (also stated in the prompt) |
| `pricing.*` | Modal Sandbox rates used for cost estimates |
| `data.*` | dataset source, test fraction, censoring cutoff, ID re-keying |
