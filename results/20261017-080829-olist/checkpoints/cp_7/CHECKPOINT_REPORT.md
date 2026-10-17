# Checkpoint 7 report

**Change:** Tried calendar features (purchase month, day of month, promised-date weekday); reverted from FEATS.
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
| $0.0415 | $0.0131 | $0.0031 | **$0.0577** | $0.4457 |

Agent time 1.0 min · 4 tool calls · code diff +10/−6 lines (`diff.patch`)

## Agent's checkpoint note

# Checkpoint 7
Change: Tried calendar features (purchase month, day of month, promised-date weekday); reverted from FEATS.
Why: Seasonal peaks and holidays may raise late rates.
Validation PR-AUC: 0.2171 -> 0.1779 (reverted state: 0.2171)
Decision: reverted, PR-AUC dropped 0.039. Training covers each calendar month once or twice, so month/day-of-month mostly memorize specific past events and don't generalize to a later period.

