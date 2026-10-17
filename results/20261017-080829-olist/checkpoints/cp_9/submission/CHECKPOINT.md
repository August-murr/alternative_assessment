# Checkpoint 9
Change: Retried product size features without category (total weight, max package volume); reverted from FEATS.
Why: Heavy or bulky parcels may ship slower; iteration 4 failed likely because of the category column.
Validation PR-AUC: 0.2318 -> 0.2289 (reverted state: 0.2318)
Decision: reverted, PR-AUC dropped 0.0029 and ROC-AUC dropped 0.6816 -> 0.6740. Product features don't help here, whether or not category is included.
