import argparse,os,pickle,pandas as pd,lightgbm as lgb
from feats import build
a=argparse.ArgumentParser();a.add_argument("--data-dir");a.add_argument("--model-dir");a=a.parse_args()
X,cols=build(a.data_dir)
y=pd.read_csv(f"{a.data_dir}/train_labels.csv")[["order_id","is_late"]]
X=X.merge(y,on="order_id")
cats=list(X.customer_state.cat.categories)
m=lgb.LGBMClassifier(verbose=-1).fit(X[cols],X.is_late)
os.makedirs(a.model_dir,exist_ok=True)
pickle.dump((m,cols,cats),open(f"{a.model_dir}/m.pkl","wb"))
