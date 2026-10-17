# Checkpoint 2 report

**Change:** Added seller features (seller state of first item, same-state flag, number of sellers).
**Status:** passed

## Scores (vs previous checkpoint)
| metric | value | change |
|---|---|---|
| validation PR-AUC (pseudo test, agent can see) | 0.2205 | ▲ +0.0154, better |
| **test PR-AUC** (held out, agent never sees) | **0.1043** | ▲ +0.0090, better |
| test ROC-AUC | 0.7363 | ▲ +0.0266, better |
| test Brier (lower is better) | 0.0364 | ▼ -0.0002, better |

Random-model test PR-AUC: 0.0378.

## Cost of this checkpoint
| Claude API (est.) | Modal agent sandbox | Modal eval sandbox | total | cumulative |
|---|---|---|---|---|
| $0.0262 | $0.0064 | $0.0023 | **$0.0348** | $0.0992 |

Agent time 0.5 min · 2 tool calls · code diff +18/−9 lines (`diff.patch`)

## Agent's checkpoint note

# Checkpoint 2
Change: Added seller features (seller state of first item, same-state flag, number of sellers).
Why: Seller-to-customer distance drives delivery time, and state match is a cheap proxy.
Validation PR-AUC: 0.2051 -> 0.2205
Decision: kept, PR-AUC improved by 0.0154.

