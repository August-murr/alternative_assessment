# Checkpoint 1 report

**Change:** Minimal baseline, default LightGBM on 7 order-level features.
**Status:** passed

## Scores (vs previous checkpoint)
| metric | value | change |
|---|---|---|
| validation PR-AUC (pseudo test, agent can see) | 0.2051 |  |
| **test PR-AUC** (held out, agent never sees) | **0.0953** |  |
| test ROC-AUC | 0.7097 |  |
| test Brier (lower is better) | 0.0366 |  |

Random-model test PR-AUC: 0.0378.

## Cost of this checkpoint
| Claude API (est.) | Modal agent sandbox | Modal eval sandbox | total | cumulative |
|---|---|---|---|---|
| $0.0528 | $0.0096 | $0.0019 | **$0.0644** | $0.0644 |

Agent time 0.8 min · 4 tool calls · code diff +57/−0 lines (`diff.patch`)

## Agent's checkpoint note

# Checkpoint 1
Change: Minimal baseline, default LightGBM on 7 order-level features.
Why: Establish a reference score and a working train/predict pipeline.
Validation PR-AUC: none -> 0.2051
Decision: kept, it is the baseline.

