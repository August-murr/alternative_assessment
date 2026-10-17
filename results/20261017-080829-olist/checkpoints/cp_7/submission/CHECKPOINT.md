# Checkpoint 7
Change: Tried calendar features (purchase month, day of month, promised-date weekday); reverted from FEATS.
Why: Seasonal peaks and holidays may raise late rates.
Validation PR-AUC: 0.2171 -> 0.1779 (reverted state: 0.2171)
Decision: reverted, PR-AUC dropped 0.039. Training covers each calendar month once or twice, so month/day-of-month mostly memorize specific past events and don't generalize to a later period.
