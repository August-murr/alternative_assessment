# Plan (one change per iteration)
1. Baseline: few order features, default LightGBM (done)
2. Seller features (done)
3. Geo distance (done, neutral/slightly negative)
4. Product features: tried, worse, reverted (retry weight/volume only later)
5. Payment features (done, neutral)
6. Time-ordered seller historical late rate / volume (past-only, out-of-fold)
7. Customer-state/route historical late rate (past-only)
8. Calendar features: month, holidays, est_days vs. typical route time
9. Hyperparameter tuning (optuna, time-split)
10. Final tuning/seed averaging, report cleanup
