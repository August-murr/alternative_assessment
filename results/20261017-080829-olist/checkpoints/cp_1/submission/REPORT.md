# Report
## Approach
LightGBM (defaults) on order-level features: item count, price sum, freight sum, promised days (estimated date - purchase time), purchase hour/day-of-week, customer state. All are known at purchase time and use only the order itself.
## Validation (pseudo test, last 20%)
- Iter 1: PR-AUC 0.2051 (ROC-AUC 0.6472, Brier 0.1057)
## Known weaknesses
Minimal baseline; no seller, geo, product or history features. Training data lacks in-transit late orders.
