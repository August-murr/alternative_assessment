# Checkpoint 10
Change: Averaged 5 LightGBM models trained with different random seeds.
Why: Subsampling makes single models noisy, so averaging should give more stable probabilities on the unseen period.
Validation PR-AUC: 0.2318 -> 0.2320
Decision: kept; the gain is negligible (+0.0002, ROC-AUC 0.6816 -> 0.6808) but it costs only seconds and reduces variance.
