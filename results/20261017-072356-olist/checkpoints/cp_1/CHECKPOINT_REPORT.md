# Checkpoint 1 report

**Change:** minimal baseline, default LightGBM on 9 order-level features
**Status:** passed

## Scores (vs previous checkpoint)
| metric | value | change |
|---|---|---|
| validation PR-AUC (pseudo test, agent can see) | 0.2564 |  |
| **test PR-AUC** (held out, agent never sees) | **0.0861** |  |
| test ROC-AUC | 0.7125 |  |
| test Brier (lower is better) | 0.036 |  |

Random-model test PR-AUC: 0.0378.

## Cost of this checkpoint
| Claude API (est.) | Modal agent sandbox | Modal eval sandbox | total | cumulative |
|---|---|---|---|---|
| $0.0889 | $0.0127 | $0.0016 | **$0.1032** | $0.1032 |

Agent time 1.0 min · 4 tool calls · code diff +46/−0 lines (`diff.patch`)

## Agent's checkpoint note

# Checkpoint 1
Change: minimal baseline, default LightGBM on 9 order-level features
Why: obvious purchase-time signals (promised days, price, freight, state, time) as a starting point.
Validation PR-AUC: none -> 0.2564
Decision: kept, it is the baseline

