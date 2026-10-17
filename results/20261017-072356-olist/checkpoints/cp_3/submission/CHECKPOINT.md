# Checkpoint 3
Change: regularized LightGBM (300 trees, lr 0.03, 15 leaves, min_child 50, subsampling, L2=5)
Why: default model overfits and the later period drifts; a smoother model should generalize better.
Validation PR-AUC: 0.2640 -> 0.2963
Decision: kept, clear gain (ROC-AUC 0.6529 -> 0.6799, Brier 0.1343 -> 0.1328)
