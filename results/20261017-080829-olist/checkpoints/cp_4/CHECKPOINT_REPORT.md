# Checkpoint 4 report

**Change:** Tried product features (first-item category, total weight, max volume); reverted.
**Status:** passed

## Scores (vs previous checkpoint)
| metric | value | change |
|---|---|---|
| validation PR-AUC (pseudo test, agent can see) | 0.2184 | = no change |
| **test PR-AUC** (held out, agent never sees) | **0.1079** | = no change |
| test ROC-AUC | 0.7454 | = no change |
| test Brier (lower is better) | 0.0364 | = no change |

Random-model test PR-AUC: 0.0378.

## Cost of this checkpoint
| Claude API (est.) | Modal agent sandbox | Modal eval sandbox | total | cumulative |
|---|---|---|---|---|
| $0.0728 | $0.0189 | $0.0018 | **$0.0935** | $0.2325 |

Agent time 1.5 min · 7 tool calls · code diff +7/−6 lines (`diff.patch`)

## Agent's checkpoint note

# Checkpoint 4
Change: Tried product features (first-item category, total weight, max volume); reverted.
Why: Package size/weight and category could affect handling and carrier time.
Validation PR-AUC: 0.2184 -> 0.2138 (reverted state: 0.2184)
Decision: reverted, PR-AUC dropped 0.0046; the high-cardinality category likely overfits. May retry weight/volume only, without category.

