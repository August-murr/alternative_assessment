# Checkpoint 8
Change: Regularized LightGBM (300 trees, lr 0.02, 15 leaves, min_child_samples 100, subsampling, L2 5) instead of defaults.
Why: Default settings overfit a small, noisy target (about 7% positives); stronger regularization generalizes better to a later period.
Validation PR-AUC: 0.2171 -> 0.2318
Decision: kept, PR-AUC improved by 0.0147 (ROC-AUC 0.6701 -> 0.6816, Brier 0.1050 -> 0.1044). Hand-picked, not searched.
