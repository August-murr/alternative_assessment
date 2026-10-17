import argparse,os,pickle,pandas as pd,lightgbm as lgb
from feats import build
a=argparse.ArgumentParser();a.add_argument("--data-dir");a.add_argument("--model-dir");a=a.parse_args()
X,cols=build(a.data_dir)
y=pd.read_csv(f"{a.data_dir}/train_labels.csv")[["order_id","is_late"]]
X=X.merge(y,on="order_id")
cats=list(X.customer_state.cat.categories)
m=lgb.LGBMClassifier(n_estimators=300,learning_rate=0.03,num_leaves=15,min_child_samples=50,subsample=0.8,subsample_freq=1,colsample_bytree=0.8,reg_lambda=5,verbose=-1).fit(X[cols],X.is_late)
os.makedirs(a.model_dir,exist_ok=True)
pickle.dump((m,cols,cats),open(f"{a.model_dir}/m.pkl","wb"))
