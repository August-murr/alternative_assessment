# Report
## Approach
LightGBM (defaults) on order-level features: item count, price sum, freight sum, promised days (estimated date - purchase time), purchase hour/day-of-week, customer state. All are known at purchase time and use only the order itself.
## Validation (pseudo test, last 20%)
- Iter 1: PR-AUC 0.2051 (ROC-AUC 0.6472, Brier 0.1057)
- Iter 2: added seller_state, same_state, n_sellers: PR-AUC 0.2205 (ROC-AUC 0.6663, Brier 0.1048)
- Iter 3: added dist_km: PR-AUC 0.2184 (ROC-AUC 0.6630, Brier 0.1049), slightly worse, kept (see CHECKPOINT)
- Iter 4: product features (category, weight, volume): PR-AUC 0.2138, worse, reverted (back to 0.2184)
- Iter 5: payment features: PR-AUC 0.2171 (ROC-AUC 0.6701, Brier 0.1050), PR-AUC slightly lower, ROC-AUC higher, kept
- Iter 6: past-only seller history (count, smoothed late rate): PR-AUC 0.2048, worse, not used (back to 0.2171). Also fixed pay_type dtype bug, no score effect.
- Iter 7: calendar features (month, day of month, est weekday): PR-AUC 0.1779, much worse, not used (back to 0.2171)
- Iter 8: regularized LightGBM params: PR-AUC 0.2318 (ROC-AUC 0.6816, Brier 0.1044), kept
- Iter 9: weight and max volume only: PR-AUC 0.2289, worse, not used (back to 0.2318)
## Known weaknesses
Minimal baseline; no seller, geo, product or history features. Training data lacks in-transit late orders.
