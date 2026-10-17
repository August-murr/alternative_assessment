import argparse, os, joblib, pandas as pd, lightgbm as lgb
from features import build, FEATS
a = argparse.ArgumentParser(); a.add_argument("--data-dir"); a.add_argument("--model-dir"); a = a.parse_args()
o = build(a.data_dir)
y = pd.read_csv(f"{a.data_dir}/train_labels.csv")[["order_id", "is_late"]]
o = o.merge(y, on="order_id")
cats = {c: list(o[c].cat.categories) for c in ["customer_state", "seller_state"]}
m = lgb.LGBMClassifier(verbose=-1).fit(o[FEATS], o.is_late)
os.makedirs(a.model_dir, exist_ok=True)
joblib.dump((m, cats), f"{a.model_dir}/model.pkl")
