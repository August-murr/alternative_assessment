# Checkpoint 6 report

**Change:** Tried past-only seller history (seller order count and smoothed late rate, using only orders delivered before each purchase); reverted from FEATS.
**Status:** passed

## Scores (vs previous checkpoint)
| metric | value | change |
|---|---|---|
| validation PR-AUC (pseudo test, agent can see) | 0.2171 | = no change |
| **test PR-AUC** (held out, agent never sees) | **0.1163** | = no change |
| test ROC-AUC | 0.7478 | = no change |
| test Brier (lower is better) | 0.0361 | = no change |

Random-model test PR-AUC: 0.0378.

## Cost of this checkpoint
| Claude API (est.) | Modal agent sandbox | Modal eval sandbox | total | cumulative |
|---|---|---|---|---|
| $0.0821 | $0.0196 | $0.0022 | **$0.1039** | $0.3881 |

Agent time 1.6 min · 7 tool calls · code diff +43/−13 lines (`diff.patch`)

## Agent's checkpoint note

# Checkpoint 6
Change: Tried past-only seller history (seller order count and smoothed late rate, using only orders delivered before each purchase); reverted from FEATS.
Why: Sellers differ persistently in lateness, so their track record should predict it.
Validation PR-AUC: 0.2171 -> 0.2048 (reverted state: 0.2171)
Decision: reverted, PR-AUC dropped 0.0123. Likely train/test mismatch: training rows see a short, noisy history, test rows see the full one. The helper code stays in features.py but is not used as features. Also fixed a bug where pay_type was never made categorical (no score change).

