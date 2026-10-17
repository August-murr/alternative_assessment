import pandas as pd
def build(d):
    o=pd.read_csv(f"{d}/orders.csv",parse_dates=["order_purchase_timestamp","order_estimated_delivery_date"])
    it=pd.read_csv(f"{d}/order_items.csv")
    c=pd.read_csv(f"{d}/customers.csv")
    g=it.groupby("order_id").agg(n_items=("order_item_id","count"),price=("price","sum"),freight=("freight_value","sum"),n_sellers=("seller_id","nunique")).reset_index()
    ge=pd.read_csv(f"{d}/geolocation.csv").groupby("geolocation_zip_code_prefix")[["geolocation_lat","geolocation_lng"]].median()
    se=pd.read_csv(f"{d}/sellers.csv")
    cz=c.set_index("customer_id").customer_zip_code_prefix
    i2=it.merge(se,on="seller_id",how="left").merge(o[["order_id","customer_id"]],on="order_id")
    i2["czip"]=i2.customer_id.map(cz)
    for p,k in(("s","seller_zip_code_prefix"),("c","czip")):
        i2[p+"lat"]=i2[k].map(ge.geolocation_lat);i2[p+"lng"]=i2[k].map(ge.geolocation_lng)
    import numpy as np
    a1,a2,b1,b2=[np.radians(i2[k]) for k in("slat","slng","clat","clng")]
    h=np.sin((b1-a1)/2)**2+np.cos(a1)*np.cos(b1)*np.sin((b2-a2)/2)**2
    i2["dist"]=6371*2*np.arcsin(np.sqrt(h))
    i2["same_state"]=(i2.seller_state==i2.customer_id.map(c.set_index("customer_id").customer_state)).astype(float)
    gd=i2.groupby("order_id").agg(dist_max=("dist","max"),dist_mean=("dist","mean"),same_state=("same_state","min")).reset_index()
    g=g.merge(gd,on="order_id",how="left")
    x=o.merge(g,on="order_id",how="left").merge(c[["customer_id","customer_state"]],on="customer_id",how="left")
    x["est_days"]=(x.order_estimated_delivery_date-x.order_purchase_timestamp).dt.total_seconds()/86400
    x["dow"]=x.order_purchase_timestamp.dt.dayofweek
    x["hour"]=x.order_purchase_timestamp.dt.hour
    x["month"]=x.order_purchase_timestamp.dt.month
    x["customer_state"]=x.customer_state.astype("category")
    cols=["n_items","price","freight","n_sellers","est_days","dow","hour","month","customer_state","dist_max","dist_mean","same_state"]
    return x[["order_id"]+cols],cols
