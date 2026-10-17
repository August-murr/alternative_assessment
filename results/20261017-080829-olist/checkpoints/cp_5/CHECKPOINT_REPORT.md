# Checkpoint 5 report

**Change:** Added payment features (max installments, total payment value, number of payments, main payment type).
**Status:** passed

## Scores (vs previous checkpoint)
| metric | value | change |
|---|---|---|
| validation PR-AUC (pseudo test, agent can see) | 0.2171 | ▼ -0.0013, worse |
| **test PR-AUC** (held out, agent never sees) | **0.1163** | ▲ +0.0084, better |
| test ROC-AUC | 0.7478 | ▲ +0.0024, better |
| test Brier (lower is better) | 0.0361 | ▼ -0.0003, better |

Random-model test PR-AUC: 0.0378.

## Cost of this checkpoint
| Claude API (est.) | Modal agent sandbox | Modal eval sandbox | total | cumulative |
|---|---|---|---|---|
| $0.0380 | $0.0112 | $0.0023 | **$0.0516** | $0.2841 |

Agent time 0.9 min · 4 tool calls · code diff +14/−9 lines (`diff.patch`)

## Agent's checkpoint note

# Checkpoint 5
Change: Added payment features (max installments, total payment value, number of payments, main payment type).
Why: Payment method affects approval delay (e.g. boleto waits for payment), which eats into the promised delivery window.
Validation PR-AUC: 0.2184 -> 0.2171
Decision: kept; PR-AUC is -0.0013 (within noise) but ROC-AUC improved 0.6630 -> 0.6701 and the signal is plausible. Revisit at tuning.

