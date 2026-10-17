# Checkpoint 6
Change: Tried past-only seller history (seller order count and smoothed late rate, using only orders delivered before each purchase); reverted from FEATS.
Why: Sellers differ persistently in lateness, so their track record should predict it.
Validation PR-AUC: 0.2171 -> 0.2048 (reverted state: 0.2171)
Decision: reverted, PR-AUC dropped 0.0123. Likely train/test mismatch: training rows see a short, noisy history, test rows see the full one. The helper code stays in features.py but is not used as features. Also fixed a bug where pay_type was never made categorical (no score change).
