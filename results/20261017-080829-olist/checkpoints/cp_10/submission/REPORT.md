# Final report

## Approach
One row per order. Features are built in `features.py` from the order, its items, payments, customer, seller and geolocation tables. A LightGBM classifier (regularized, 5-seed average) predicts `p_late`. `train.py` fits and saves the models; `predict.py` rebuilds the same features and averages the models.

## Final features (all known at purchase time, using only the order itself)
- n_items, price sum, freight sum, n_sellers
- est_days: promised delivery date minus purchase time (the promise is made at purchase)
- purchase hour and weekday
- customer_state, seller_state (first item), same_state flag
- dist_km: seller to customer haversine distance, from mean coordinates per zip prefix in `geolocation.csv`
- payment: max installments, total payment value, number of payments, main payment type

No label, delivery date or other post-purchase column is used as a model input. No feature uses other orders in the file being predicted. `train_labels.csv` is only read as the training target. Nothing is hardcoded.

## Model
LightGBM: 300 trees, lr 0.02, 15 leaves, min_child_samples 100, subsample 0.8, colsample 0.7, L2 5, 5 seeds averaged. Training takes a few seconds, prediction about 2 seconds.

## Validation (pseudo test, last 20% of orders; positive rate 11.9%)
| iter | change | PR-AUC | decision |
|---|---|---|---|
| 1 | baseline, 7 features, default LGBM | 0.2051 | kept |
| 2 | seller state, same-state, n_sellers | 0.2205 | kept |
| 3 | seller-customer distance | 0.2184 | kept (within noise) |
| 4 | product category, weight, volume | 0.2138 | reverted |
| 5 | payment features | 0.2171 | kept (ROC-AUC up) |
| 6 | past-only seller history | 0.2048 | not used |
| 7 | month, day of month, est weekday | 0.1779 | not used |
| 8 | regularized LightGBM | 0.2318 | kept |
| 9 | weight, max volume only | 0.2289 | not used |
| 10 | 5-seed averaging | 0.2320 | kept |

Final pseudo-test scores: PR-AUC 0.2320, ROC-AUC 0.6808, Brier 0.1044.

## Known weaknesses
- Signal is weak overall (ROC-AUC about 0.68). Most lateness comes from carrier events we cannot see at purchase.
- Pseudo-test differences of about 0.002 are within noise (about 1.5k positives), so iterations 3 and 5 were kept on plausibility, not clear gains.
- Distribution shift: the training snapshot lacks late orders still in transit, and the late rate in the later period differs (6.9% overall vs 11.9% in the last 20%). Probabilities are likely under-calibrated for the test period.
- Time-based features (month) and history features (seller late rate) hurt, so the model has no information about seller track record or seasonality. A better history feature (out-of-fold, matched between train and test) is the main untried idea.
- Dead helper code (`hist_train`, `hist_apply`) remains in `features.py`; its output columns are not in `FEATS`.
- Hyperparameters were hand-picked, not searched.
