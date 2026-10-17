# Autonomous agent ML engineering: leakage-safe, reproducible, cost-tracked

An autonomous **Claude Code** agent works alone in a Modal sandbox and writes a **training script** that predicts late deliveries on the [Olist e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). It works in short, verified iterations. Each checkpoint is retrained from scratch in a **network-blocked** sandbox and scored on a later, held-out time period. Test labels never enter any sandbox, and the agent never sees test scores.

Because the submission is code rather than a model, every result can be reproduced and audited for data leakage. Alongside that, the pipeline tracks **how much each checkpoint costs** (Claude API + Modal compute) against the score it reaches.

**Test run** (3 iterations, Sonnet 5.5 at low effort): test PR-AUC rose **0.086 → 0.093 → 0.112** over three verified checkpoints, against 0.038 for a random model. Total cost was **$0.18**: 78% Claude API, 22% Modal.

![Score and cumulative cost per checkpoint](results/20261017-072356-olist/cost_curve.png)

## Read next
- **[docs/REPORT.md](docs/REPORT.md)**: results, cost analysis, and what we learned about the agent, including a leak caught in an earlier run
- **[docs/DOCUMENTATION.md](docs/DOCUMENTATION.md)**: how it works, safeguards, how to run it, configuration
- [docs/LEAKAGE.md](docs/LEAKAGE.md): the data decisions and their evidence
- [results/](results/): per-checkpoint reports, code diffs and submissions

## Safeguards at a glance

| Risk | Control |
|---|---|
| Post-purchase information in features | removed from the data (reviews, delivery and approval dates, a derived deadline column), plus a prompt rule and code review |
| Seeing the test set | temporal split; test data exists only in the eval sandbox, labels only on the host |
| Fetching the data or labels at eval time | evaluation runs with `block_network=True`; IDs are re-keyed with a secret salt |
| Agent misuse of its environment | 8 tools only, no skills, credentials scrubbed from its shell, no telemetry |
| Unverified progress | every checkpoint must pass the same harness the evaluator uses before the next iteration |

## Run it
```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env                       # Modal + Claude Code tokens, data salt
.venv/bin/python -m pipeline.data.download && .venv/bin/python -m pipeline.data.prepare
.venv/bin/python -u -m pipeline.run --iterations 3 > runs/live.log 2>&1    # watch: tail -f runs/live.log
```
