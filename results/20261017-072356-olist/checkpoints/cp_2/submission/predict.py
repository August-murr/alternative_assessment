import argparse,pickle,pandas as pd
from feats import build
a=argparse.ArgumentParser();a.add_argument("--model-dir");a.add_argument("--data-dir");a.add_argument("--output");a=a.parse_args()
m,cols,cats=pickle.load(open(f"{a.model_dir}/m.pkl","rb"))
X,_=build(a.data_dir)
X["customer_state"]=pd.Categorical(X.customer_state.astype(object),categories=cats)
X["p_late"]=m.predict_proba(X[cols])[:,1].clip(0,1)
X[["order_id","p_late"]].to_csv(a.output,index=False)
