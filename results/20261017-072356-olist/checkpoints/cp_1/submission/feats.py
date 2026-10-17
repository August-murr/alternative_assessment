import pandas as pd
def build(d):
    o=pd.read_csv(f"{d}/orders.csv",parse_dates=["order_purchase_timestamp","order_estimated_delivery_date"])
    it=pd.read_csv(f"{d}/order_items.csv")
    c=pd.read_csv(f"{d}/customers.csv")
    g=it.groupby("order_id").agg(n_items=("order_item_id","count"),price=("price","sum"),freight=("freight_value","sum"),n_sellers=("seller_id","nunique")).reset_index()
    x=o.merge(g,on="order_id",how="left").merge(c[["customer_id","customer_state"]],on="customer_id",how="left")
    x["est_days"]=(x.order_estimated_delivery_date-x.order_purchase_timestamp).dt.total_seconds()/86400
    x["dow"]=x.order_purchase_timestamp.dt.dayofweek
    x["hour"]=x.order_purchase_timestamp.dt.hour
    x["month"]=x.order_purchase_timestamp.dt.month
    x["customer_state"]=x.customer_state.astype("category")
    cols=["n_items","price","freight","n_sellers","est_days","dow","hour","month","customer_state"]
    return x[["order_id"]+cols],cols
