import argparse, joblib, pandas as pd
from features import build, FEATS
a = argparse.ArgumentParser(); a.add_argument("--model-dir"); a.add_argument("--data-dir"); a.add_argument("--output"); a = a.parse_args()
m, cats = joblib.load(f"{a.model_dir}/model.pkl")
o = build(a.data_dir)
o["customer_state"] = pd.Categorical(o.customer_state.astype(object), categories=cats)
o["p_late"] = m.predict_proba(o[FEATS])[:, 1]
o[["order_id", "p_late"]].to_csv(a.output, index=False)
