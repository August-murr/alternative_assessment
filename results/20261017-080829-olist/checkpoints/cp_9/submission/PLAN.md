# Plan (one change per iteration)
1. Baseline: few order features, default LightGBM (done)
2. Seller features (done)
3. Geo distance (done, neutral/slightly negative)
4. Product features: tried, worse, reverted (retry weight/volume only later)
5. Payment features (done, neutral)
6. Seller history: tried, worse, not used (history mismatch between train and test; maybe retry with out-of-fold)
7. Customer-state/route historical late rate (past-only)
8. Calendar features: tried, much worse, not used (memorizes past events)
9. Regularized params (done, hand-picked); next: small search of params, then retry weight/volume features
10. Final tuning/seed averaging, report cleanup
- Iter 9 retry of weight\/volume: worse, dropped. Product features are closed.
