# Checkpoint 9 report

**Change:** Retried product size features without category (total weight, max package volume); reverted from FEATS.
**Status:** passed

## Scores (vs previous checkpoint)
| metric | value | change |
|---|---|---|
| validation PR-AUC (pseudo test, agent can see) | 0.2318 | = no change |
| **test PR-AUC** (held out, agent never sees) | **0.1238** | = no change |
| test ROC-AUC | 0.7688 | = no change |
| test Brier (lower is better) | 0.0355 | = no change |

Random-model test PR-AUC: 0.0378.

## Cost of this checkpoint
| Claude API (est.) | Modal agent sandbox | Modal eval sandbox | total | cumulative |
|---|---|---|---|---|
| $0.0296 | $0.0106 | $0.0030 | **$0.0432** | $0.5263 |

Agent time 0.8 min · 2 tool calls · code diff +12/−6 lines (`diff.patch`)

## Agent's checkpoint note

# Checkpoint 9
Change: Retried product size features without category (total weight, max package volume); reverted from FEATS.
Why: Heavy or bulky parcels may ship slower; iteration 4 failed likely because of the category column.
Validation PR-AUC: 0.2318 -> 0.2289 (reverted state: 0.2318)
Decision: reverted, PR-AUC dropped 0.0029 and ROC-AUC dropped 0.6816 -> 0.6740. Product features don't help here, whether or not category is included.

