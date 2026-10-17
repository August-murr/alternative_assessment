# Results

| run | what | test PR-AUC (first → best → final) | cost |
|---|---|---|---|
| [20261017-080829-olist](20261017-080829-olist/SUMMARY.md) | 10 iterations, Sonnet 5.5, low effort | 0.095 → 0.124 → 0.123 | $0.58 |

The run folder contains:
- `SUMMARY.md`: progress table, chart and the agent's final report
- `cost_curve.png`
- `progress.csv`
- `run.json`: the full configuration
- `prompt.md`: the exact first prompt
- `checkpoints/cp_<k>/`: `CHECKPOINT_REPORT.md`, `diff.patch` and the submission code at that point

The run uses the final, embargoed dataset (see [docs/LEAKAGE.md](../docs/LEAKAGE.md)).
