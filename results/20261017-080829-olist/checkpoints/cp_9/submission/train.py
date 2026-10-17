import argparse, os, joblib, pandas as pd, lightgbm as lgb
from features import build, FEATS, hist_train
a = argparse.ArgumentParser(); a.add_argument("--data-dir"); a.add_argument("--model-dir"); a = a.parse_args()
o = build(a.data_dir)
lab = pd.read_csv(f"{a.data_dir}/train_labels.csv")
o, table, prior = hist_train(o, lab)
cats = {c: list(o[c].cat.categories) for c in ["customer_state", "seller_state", "pay_type"]}
m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.02, num_leaves=15, min_child_samples=100, subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_lambda=5, verbose=-1).fit(o[FEATS], o.is_late)
os.makedirs(a.model_dir, exist_ok=True)
joblib.dump((m, cats, table, prior), f"{a.model_dir}/model.pkl")
