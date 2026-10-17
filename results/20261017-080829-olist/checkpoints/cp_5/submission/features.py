import numpy as np
import pandas as pd

def build(d):
    o = pd.read_csv(f"{d}/orders.csv", parse_dates=["order_purchase_timestamp", "order_estimated_delivery_date"])
    it = pd.read_csv(f"{d}/order_items.csv")
    c = pd.read_csv(f"{d}/customers.csv")
    s = pd.read_csv(f"{d}/sellers.csv")
    it = it.merge(s[["seller_id", "seller_state", "seller_zip_code_prefix"]], on="seller_id", how="left")
    first = it.sort_values("order_item_id").groupby("order_id").seller_state.first().rename("seller_state")
    szip = it.sort_values("order_item_id").groupby("order_id").seller_zip_code_prefix.first()
    nsel = it.groupby("order_id").seller_id.nunique().rename("n_sellers")
    pay = pd.read_csv(f"{d}/order_payments.csv")
    pg = pay.groupby("order_id").agg(installments=("payment_installments", "max"), pay_value=("payment_value", "sum"), n_pay=("payment_sequential", "count"))
    ptype = pay.sort_values("payment_value", ascending=False).groupby("order_id").payment_type.first().rename("pay_type")
    g = it.groupby("order_id").agg(n_items=("order_item_id", "count"), price=("price", "sum"), freight=("freight_value", "sum"))
    g = g.join(first).join(szip).join(nsel).join(pg).join(ptype)
    o = o.merge(g, on="order_id", how="left").merge(c[["customer_id", "customer_state", "customer_zip_code_prefix"]], on="customer_id", how="left")
    geo = pd.read_csv(f"{d}/geolocation.csv").groupby("geolocation_zip_code_prefix")[["geolocation_lat", "geolocation_lng"]].mean()
    for p, col in (("c", "customer_zip_code_prefix"), ("s", "seller_zip_code_prefix")):
        o[p + "lat"] = o[col].map(geo.geolocation_lat)
        o[p + "lng"] = o[col].map(geo.geolocation_lng)
    la1, la2, dl = np.radians(o.clat), np.radians(o.slat), np.radians(o.slng - o.clng)
    cosd = np.sin(la1) * np.sin(la2) + np.cos(la1) * np.cos(la2) * np.cos(dl)
    o["dist_km"] = 6371 * np.arccos(np.clip(cosd, -1, 1))
    t = o.order_purchase_timestamp
    o["est_days"] = (o.order_estimated_delivery_date - t).dt.total_seconds() / 86400
    o["hour"] = t.dt.hour
    o["dow"] = t.dt.dayofweek
    o["same_state"] = (o.customer_state == o.seller_state).astype(float)
    o["customer_state"] = o.customer_state.astype("category")
    o["seller_state"] = o.seller_state.astype("category")
    o["pay_type"] = o.pay_type.astype("category")
    return o

FEATS = ["n_items", "price", "freight", "est_days", "hour", "dow", "customer_state", "seller_state", "same_state", "n_sellers", "dist_km", "installments", "pay_value", "n_pay", "pay_type"]
