# Checkpoint 5
Change: Added payment features (max installments, total payment value, number of payments, main payment type).
Why: Payment method affects approval delay (e.g. boleto waits for payment), which eats into the promised delivery window.
Validation PR-AUC: 0.2184 -> 0.2171
Decision: kept; PR-AUC is -0.0013 (within noise) but ROC-AUC improved 0.6630 -> 0.6701 and the signal is plausible. Revisit at tuning.
