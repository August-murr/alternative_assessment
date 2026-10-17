import argparse, joblib, pandas as pd
from features import build, FEATS, hist_apply
a = argparse.ArgumentParser(); a.add_argument("--model-dir"); a.add_argument("--data-dir"); a.add_argument("--output"); a = a.parse_args()
m, cats, table, prior = joblib.load(f"{a.model_dir}/model.pkl")
o = build(a.data_dir)
o = hist_apply(o, table, prior)
for c, cc in cats.items():
    o[c] = pd.Categorical(o[c].astype(object), categories=cc)
o["p_late"] = m.predict_proba(o[FEATS])[:, 1]
o[["order_id", "p_late"]].to_csv(a.output, index=False)
