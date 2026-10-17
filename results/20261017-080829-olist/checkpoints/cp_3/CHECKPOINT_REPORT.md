# Checkpoint 3 report

**Change:** Added seller-to-customer haversine distance (km) from mean geolocation per zip prefix.
**Status:** passed

## Scores (vs previous checkpoint)
| metric | value | change |
|---|---|---|
| validation PR-AUC (pseudo test, agent can see) | 0.2184 | ▼ -0.0021, worse |
| **test PR-AUC** (held out, agent never sees) | **0.1079** | ▲ +0.0036, better |
| test ROC-AUC | 0.7454 | ▲ +0.0091, better |
| test Brier (lower is better) | 0.0364 | = no change |

Random-model test PR-AUC: 0.0378.

## Cost of this checkpoint
| Claude API (est.) | Modal agent sandbox | Modal eval sandbox | total | cumulative |
|---|---|---|---|---|
| $0.0302 | $0.0073 | $0.0023 | **$0.0398** | $0.1390 |

Agent time 0.6 min · 2 tool calls · code diff +20/−10 lines (`diff.patch`)

## Agent's checkpoint note

# Checkpoint 3
Change: Added seller-to-customer haversine distance (km) from mean geolocation per zip prefix.
Why: Distance is a main driver of shipping time and promised-date tightness.
Validation PR-AUC: 0.2205 -> 0.2184
Decision: kept, although slightly worse (-0.0021, within likely noise for ~1.5k positives); distance is causally meaningful and later route/history features build on it. Revisit if it keeps hurting.

