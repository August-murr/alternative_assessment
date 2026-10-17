# Checkpoint 3 report

**Change:** regularized LightGBM (300 trees, lr 0.03, 15 leaves, min_child 50, subsampling, L2=5)
**Status:** passed

## Scores (vs previous checkpoint)
| metric | value | change |
|---|---|---|
| validation PR-AUC (pseudo test, agent can see) | 0.2963 | ▲ +0.0323, better |
| **test PR-AUC** (held out, agent never sees) | **0.112** | ▲ +0.0187, better |
| test ROC-AUC | 0.7544 | ▲ +0.0294, better |
| test Brier (lower is better) | 0.0351 | ▼ -0.0006, better |

Random-model test PR-AUC: 0.0378.

## Cost of this checkpoint
| Claude API (est.) | Modal agent sandbox | Modal eval sandbox | total | cumulative |
|---|---|---|---|---|
| $0.0268 | $0.0101 | $0.0029 | **$0.0398** | $0.1840 |

Agent time 0.8 min · 2 tool calls · code diff +25/−17 lines (`diff.patch`)

## Agent's checkpoint note

# Checkpoint 3
Change: regularized LightGBM (300 trees, lr 0.03, 15 leaves, min_child 50, subsampling, L2=5)
Why: default model overfits and the later period drifts; a smoother model should generalize better.
Validation PR-AUC: 0.2640 -> 0.2963
Decision: kept, clear gain (ROC-AUC 0.6529 -> 0.6799, Brier 0.1343 -> 0.1328)

