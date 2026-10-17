# Checkpoint 2
Change: added seller-customer geo features (max/mean haversine distance, same-state flag)
Why: longer shipping routes should raise late risk; zip-prefix coordinates come from geolocation.csv, known at purchase.
Validation PR-AUC: 0.2564 -> 0.2640
Decision: kept, small gain (ROC-AUC 0.6494 -> 0.6529, Brier 0.1345 -> 0.1343)
