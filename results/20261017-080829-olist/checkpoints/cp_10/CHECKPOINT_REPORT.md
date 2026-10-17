# Checkpoint 10 report

**Change:** Averaged 5 LightGBM models trained with different random seeds.
**Status:** passed

## Scores (vs previous checkpoint)
| metric | value | change |
|---|---|---|
| validation PR-AUC (pseudo test, agent can see) | 0.232 | ▲ +0.0002, better |
| **test PR-AUC** (held out, agent never sees) | **0.1229** | ▼ -0.0009, worse |
| test ROC-AUC | 0.7675 | ▼ -0.0013, worse |
| test Brier (lower is better) | 0.0356 | ▲ +0.0001, worse |

Random-model test PR-AUC: 0.0378.

## Cost of this checkpoint
| Claude API (est.) | Modal agent sandbox | Modal eval sandbox | total | cumulative |
|---|---|---|---|---|
| $0.0451 | $0.0105 | $0.0026 | **$0.0582** | $0.5845 |

Agent time 0.8 min · 2 tool calls · code diff +47/−20 lines (`diff.patch`)

## Agent's checkpoint note

# Checkpoint 10
Change: Averaged 5 LightGBM models trained with different random seeds.
Why: Subsampling makes single models noisy, so averaging should give more stable probabilities on the unseen period.
Validation PR-AUC: 0.2318 -> 0.2320
Decision: kept; the gain is negligible (+0.0002, ROC-AUC 0.6816 -> 0.6808) but it costs only seconds and reduces variance.

