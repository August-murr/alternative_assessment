# Checkpoint 8 report

**Change:** Regularized LightGBM (300 trees, lr 0.02, 15 leaves, min_child_samples 100, subsampling, L2 5) instead of defaults.
**Status:** passed

## Scores (vs previous checkpoint)
| metric | value | change |
|---|---|---|
| validation PR-AUC (pseudo test, agent can see) | 0.2318 | ▲ +0.0147, better |
| **test PR-AUC** (held out, agent never sees) | **0.1238** | ▲ +0.0075, better |
| test ROC-AUC | 0.7688 | ▲ +0.0210, better |
| test Brier (lower is better) | 0.0355 | ▼ -0.0006, better |

Random-model test PR-AUC: 0.0378.

## Cost of this checkpoint
| Claude API (est.) | Modal agent sandbox | Modal eval sandbox | total | cumulative |
|---|---|---|---|---|
| $0.0269 | $0.0077 | $0.0028 | **$0.0373** | $0.4831 |

Agent time 0.6 min · 2 tool calls · code diff +8/−7 lines (`diff.patch`)

## Agent's checkpoint note

# Checkpoint 8
Change: Regularized LightGBM (300 trees, lr 0.02, 15 leaves, min_child_samples 100, subsampling, L2 5) instead of defaults.
Why: Default settings overfit a small, noisy target (about 7% positives); stronger regularization generalizes better to a later period.
Validation PR-AUC: 0.2171 -> 0.2318
Decision: kept, PR-AUC improved by 0.0147 (ROC-AUC 0.6701 -> 0.6816, Brier 0.1050 -> 0.1044). Hand-picked, not searched.

