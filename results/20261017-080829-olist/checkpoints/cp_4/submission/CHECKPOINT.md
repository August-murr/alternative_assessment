# Checkpoint 4
Change: Tried product features (first-item category, total weight, max volume); reverted.
Why: Package size/weight and category could affect handling and carrier time.
Validation PR-AUC: 0.2184 -> 0.2138 (reverted state: 0.2184)
Decision: reverted, PR-AUC dropped 0.0046; the high-cardinality category likely overfits. May retry weight/volume only, without category.
