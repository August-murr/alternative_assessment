# Report
Baseline (iter 1): LightGBM defaults on order-level features: item count, price sum, freight sum, seller count, promised days (estimated date - purchase time), purchase dow/hour/month, customer state. All known at purchase time; no cross-order features.
Weaknesses: no seller/geo/product features, no tuning.

## Iter 1 validation
PR-AUC 0.2564, ROC-AUC 0.6494, Brier 0.1345 (pseudo test positive rate 15.7% vs 7.8% overall, so there is drift).
