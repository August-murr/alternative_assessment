# Checkpoint 3
Change: Added seller-to-customer haversine distance (km) from mean geolocation per zip prefix.
Why: Distance is a main driver of shipping time and promised-date tightness.
Validation PR-AUC: 0.2205 -> 0.2184
Decision: kept, although slightly worse (-0.0021, within likely noise for ~1.5k positives); distance is causally meaningful and later route/history features build on it. Revisit if it keeps hurting.
