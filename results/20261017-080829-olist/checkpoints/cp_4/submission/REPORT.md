# Report
## Approach
LightGBM (defaults) on order-level features: item count, price sum, freight sum, promised days (estimated date - purchase time), purchase hour/day-of-week, customer state. All are known at purchase time and use only the order itself.
## Validation (pseudo test, last 20%)
- Iter 1: PR-AUC 0.2051 (ROC-AUC 0.6472, Brier 0.1057)
- Iter 2: added seller_state, same_state, n_sellers: PR-AUC 0.2205 (ROC-AUC 0.6663, Brier 0.1048)
- Iter 3: added dist_km: PR-AUC 0.2184 (ROC-AUC 0.6630, Brier 0.1049), slightly worse, kept (see CHECKPOINT)
- Iter 4: product features (category, weight, volume): PR-AUC 0.2138, worse, reverted (back to 0.2184)
## Known weaknesses
Minimal baseline; no seller, geo, product or history features. Training data lacks in-transit late orders.
