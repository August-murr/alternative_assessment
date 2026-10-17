# Plan (one change per iteration)
1. Baseline: few order features, default LightGBM (done)
2. Seller features (done)
3. Geo distance seller->customer via geolocation
4. Product features: category, weight, volume
5. Payment features: type, installments, value
6. Time-ordered seller historical late rate / volume (past-only, out-of-fold)
7. Customer-state/route historical late rate (past-only)
8. Calendar features: month, holidays, est_days vs. typical route time
9. Hyperparameter tuning (optuna, time-split)
10. Final tuning/seed averaging, report cleanup
