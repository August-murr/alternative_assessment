# Checkpoint 2 report

**Change:** added seller-customer geo features (max/mean haversine distance, same-state flag)
**Status:** passed

## Scores (vs previous checkpoint)
| metric | value | change |
|---|---|---|
| validation PR-AUC (pseudo test, agent can see) | 0.264 | ▲ +0.0076, better |
| **test PR-AUC** (held out, agent never sees) | **0.0933** | ▲ +0.0072, better |
| test ROC-AUC | 0.725 | ▲ +0.0125, better |
| test Brier (lower is better) | 0.0357 | ▼ -0.0003, better |

Random-model test PR-AUC: 0.0378.

## Cost of this checkpoint
| Claude API (est.) | Modal agent sandbox | Modal eval sandbox | total | cumulative |
|---|---|---|---|---|
| $0.0284 | $0.0098 | $0.0028 | **$0.0410** | $0.1443 |

Agent time 0.8 min · 2 tool calls · code diff +23/−6 lines (`diff.patch`)

## Agent's checkpoint note

# Checkpoint 2
Change: added seller-customer geo features (max/mean haversine distance, same-state flag)
Why: longer shipping routes should raise late risk; zip-prefix coordinates come from geolocation.csv, known at purchase.
Validation PR-AUC: 0.2564 -> 0.2640
Decision: kept, small gain (ROC-AUC 0.6494 -> 0.6529, Brier 0.1345 -> 0.1343)

