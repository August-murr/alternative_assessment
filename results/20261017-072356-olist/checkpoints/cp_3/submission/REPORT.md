# Final report
## Approach
LightGBM classifier on order-level features, trained on all labelled orders (train.py), shared feature code in feats.py.
## Features (all known at purchase time; each row uses only its own order plus static lookup tables)
- Items: count, total price, total freight, number of sellers.
- Promised delivery days (estimated date minus purchase time); purchase day of week, hour, month.
- Customer state.
- Geo: max/mean haversine distance seller-to-customer (median coordinates per zip prefix), same-state flag.
No labels, delivery dates or cross-order aggregates are used as inputs.
## Validation (last 20% of orders held out; PR-AUC)
- Iter 1 baseline default LightGBM: 0.2564 (ROC 0.6494, Brier 0.1345)
- Iter 2 + geo features: 0.2640 (ROC 0.6529, Brier 0.1343)
- Iter 3 regularized LightGBM: 0.2963 (ROC 0.6799, Brier 0.1328)
## Known weaknesses
- Held-out late rate (15.7%) is double the overall 7.8%, so there is drift; scores are only a guide.
- No seller/product history features (seller historical late rate, product weight/volume, category), and no hyperparameter search.
- Month feature may extrapolate poorly to unseen periods.
