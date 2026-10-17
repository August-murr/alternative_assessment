# Autonomous agent ML engineering: leakage-safe, reproducible, cost-tracked

An autonomous **Claude Code** agent works alone in a Modal sandbox and writes a **training script** that predicts late deliveries on the [Olist e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). It works in short, verified iterations. Each checkpoint is retrained from scratch in a **network-blocked** sandbox and scored on a later, held-out time period. Test labels never enter any sandbox, and the agent never sees test scores.

Because the submission is code rather than a model, every result can be reproduced and audited for data leakage. Alongside that, the pipeline tracks **how much each checkpoint costs** (Claude API + Modal compute) against the score it reaches.

**Result** (10 iterations, Sonnet 5.5 at low effort): all 10 checkpoints were verified. Test PR-AUC rose from **0.095 to 0.124** (final 0.123), 3.3× a random model, for **$0.58** in total (76% Claude API, 24% Modal). Returns diminished quickly: half the budget delivered 74% of the gain, and the four experiments the agent tried and reverted cost half the run.

Reading the agent's code exposed two leaks that a score-only evaluation would have rewarded. One was in the agent's own early code; the other was in *our* train/test split, and the agent's time-aware features are what revealed it ([report §5](docs/REPORT.md#5-findings)).

![Held-out score vs spend, stacked by cost source](results/20261017-080829-olist/cost_curve.png)

## Read next
- **[docs/REPORT.md](docs/REPORT.md)**: results, cost analysis, and findings about the agent and the leaks
- **[docs/DOCUMENTATION.md](docs/DOCUMENTATION.md)**: how it works, safeguards, how to run it, configuration
- [docs/LEAKAGE.md](docs/LEAKAGE.md): the data decisions and their evidence
- [results/](results/): per-checkpoint reports, code diffs and submissions

## Safeguards at a glance

| Risk | Control |
|---|---|
| Post-purchase information in features | removed from the data (reviews, delivery and approval dates, a derived deadline column), plus a prompt rule and code review |
| Training labels the model couldn't have known yet | label embargo: training outcomes resolved after the split boundary are dropped |
| Seeing the test set | temporal split; test data exists only in the eval sandbox, labels only on the host |
| Fetching the data or labels at eval time | evaluation runs with `block_network=True`; IDs are re-keyed with a secret salt |
| Agent misuse of its environment | 8 tools only, no skills, credentials scrubbed from its shell, no telemetry |
| Unverified progress | every checkpoint must pass the same harness the evaluator uses before the next iteration |

## Run it
```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env                       # Modal + Claude Code tokens, data salt
.venv/bin/python -m pipeline.data.download && .venv/bin/python -m pipeline.data.prepare
.venv/bin/python -u -m pipeline.run > runs/live.log 2>&1    # 10 iterations (config.yaml); watch: tail -f runs/live.log
```
