import pandas as pd

def build(d):
    o = pd.read_csv(f"{d}/orders.csv", parse_dates=["order_purchase_timestamp", "order_estimated_delivery_date"])
    it = pd.read_csv(f"{d}/order_items.csv")
    c = pd.read_csv(f"{d}/customers.csv")
    s = pd.read_csv(f"{d}/sellers.csv")
    it = it.merge(s[["seller_id", "seller_state"]], on="seller_id", how="left")
    first = it.sort_values("order_item_id").groupby("order_id").seller_state.first().rename("seller_state")
    nsel = it.groupby("order_id").seller_id.nunique().rename("n_sellers")
    g = it.groupby("order_id").agg(n_items=("order_item_id", "count"), price=("price", "sum"), freight=("freight_value", "sum"))
    g = g.join(first).join(nsel)
    o = o.merge(g, on="order_id", how="left").merge(c[["customer_id", "customer_state"]], on="customer_id", how="left")
    t = o.order_purchase_timestamp
    o["est_days"] = (o.order_estimated_delivery_date - t).dt.total_seconds() / 86400
    o["hour"] = t.dt.hour
    o["dow"] = t.dt.dayofweek
    o["same_state"] = (o.customer_state == o.seller_state).astype(float)
    o["customer_state"] = o.customer_state.astype("category")
    o["seller_state"] = o.seller_state.astype("category")
    return o

FEATS = ["n_items", "price", "freight", "est_days", "hour", "dow", "customer_state", "seller_state", "same_state", "n_sellers"]
