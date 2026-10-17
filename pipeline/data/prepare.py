"""Build the leakage-free, temporally split dataset.

Outputs under data/processed/:
  train/            feature tables + train_labels.csv          (goes to the agent sandbox)
  test_features/    same feature tables, no labels              (given to the submitted script at eval time)
  test_labels.csv   order_id, is_late                           (evaluator only)
  metadata.json     split details, counts, dropped columns, file hashes

See docs/LEAKAGE.md for the reasoning behind every dropped column.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

from pipeline.config import env, load_config

# Prediction time = order purchase. Only information known at that moment may be a feature.
ORDERS_KEEP = ["order_id", "customer_id", "order_purchase_timestamp", "order_estimated_delivery_date"]
DROPPED = {
    "olist_order_reviews_dataset": "entire table: written after delivery; late orders get much lower scores",
    "olist_orders_dataset.order_status": "post-hoc; used only to keep delivered orders",
    "olist_orders_dataset.order_approved_at": "post-purchase (payment approval lags up to days)",
    "olist_orders_dataset.order_delivered_carrier_date": "post-purchase; moved to train_labels.csv only",
    "olist_orders_dataset.order_delivered_customer_date": "defines the label; moved to train_labels.csv only",
    "olist_order_items_dataset.shipping_limit_date": "computed as order_approved_at + N days, so encodes post-purchase approval time",
}
ID_COLUMNS = ["order_id", "customer_id", "customer_unique_id", "product_id", "seller_id"]
LATE_MARGIN_QUANTILE = 0.9   # how long after the estimate late orders usually arrive
CENSOR_MIN_COMPLETE = 0.95   # share of a purchase day's orders whose lateness must be observable


def read(raw: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(raw / f"{name}.csv")


def label_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Delivered orders with a delivery date, plus is_late (day-level, since estimates are midnight dates)."""
    for col in ["order_purchase_timestamp", "order_delivered_carrier_date",
                "order_delivered_customer_date", "order_estimated_delivery_date"]:
        orders[col] = pd.to_datetime(orders[col])
    delivered = orders[(orders["order_status"] == "delivered") & orders["order_delivered_customer_date"].notna()].copy()
    delivered["is_late"] = (
        delivered["order_delivered_customer_date"].dt.normalize() > delivered["order_estimated_delivery_date"]
    ).astype(int)
    return delivered


def auto_censor_cutoff(orders: pd.DataFrame, delivered: pd.DataFrame) -> tuple[pd.Timestamp, dict]:
    """First purchase day (in 2018) whose lateness we can't reliably observe.

    snapshot: last day with a normal volume of recorded deliveries.
    margin:   90th percentile of days-late among late deliveries.
    An order's label is observable if estimated_delivery + margin <= snapshot; the cutoff is the
    first purchase day where fewer than 95% of orders satisfy that.
    """
    daily = delivered["order_delivered_customer_date"].dt.normalize().value_counts().sort_index()
    threshold = 0.1 * daily[daily.index >= "2018-01-01"].median()
    snapshot = daily[daily >= threshold].index.max()

    late = delivered[delivered["is_late"] == 1]
    days_late = (late["order_delivered_customer_date"].dt.normalize() - late["order_estimated_delivery_date"]).dt.days
    margin = int(days_late.quantile(LATE_MARGIN_QUANTILE))

    observable = orders["order_estimated_delivery_date"] + pd.Timedelta(days=margin) <= snapshot
    share = observable.groupby(orders["order_purchase_timestamp"].dt.normalize()).mean()
    bad_days = share[(share < CENSOR_MIN_COMPLETE) & (share.index >= "2018-01-01")]
    cutoff = bad_days.index.min()
    return cutoff, {"snapshot": str(snapshot.date()), "late_margin_days": margin,
                    "min_observable_share": CENSOR_MIN_COMPLETE}


def rekey(df: pd.DataFrame, salt: str) -> pd.DataFrame:
    for col in ID_COLUMNS:
        if col in df.columns:
            df[col] = [hashlib.sha256(f"{salt}:{col}:{v}".encode()).hexdigest()[:16] for v in df[col]]
    return df


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    cfg = load_config()
    raw, out = cfg.data.raw_dir, cfg.data.processed_dir

    orders = read(raw, "olist_orders_dataset")
    delivered = label_orders(orders)

    if cfg.data.censor_cutoff == "auto":
        cutoff, censor_info = auto_censor_cutoff(orders, delivered)
    else:
        cutoff, censor_info = pd.Timestamp(cfg.data.censor_cutoff), {"manual": True}
    kept = delivered[delivered["order_purchase_timestamp"] < cutoff].sort_values(
        ["order_purchase_timestamp", "order_id"], kind="stable").reset_index(drop=True)

    # Last test_fraction of orders by purchase time -> test. Ties at the boundary go to test.
    boundary = kept["order_purchase_timestamp"].iloc[int(len(kept) * (1 - cfg.data.test_fraction))]
    is_test = kept["order_purchase_timestamp"] >= boundary
    split_ids = {"train": set(kept.loc[~is_test, "order_id"]), "test": set(kept.loc[is_test, "order_id"])}

    items = read(raw, "olist_order_items_dataset").drop(columns=["shipping_limit_date"])
    payments = read(raw, "olist_order_payments_dataset")
    customers = read(raw, "olist_customers_dataset")
    products = read(raw, "olist_products_dataset")
    sellers = read(raw, "olist_sellers_dataset")
    geolocation = read(raw, "olist_geolocation_dataset")
    categories = read(raw, "product_category_name_translation")

    salt = env("DATA_SALT")
    if cfg.data.rekey_ids and not salt:
        raise SystemExit("rekey_ids is on but DATA_SALT is not set in .env")

    if out.exists():
        shutil.rmtree(out)
    stats = {}
    for split, ids in split_ids.items():
        o = kept[kept["order_id"].isin(ids)]
        it = items[items["order_id"].isin(ids)]
        tables = {
            "orders": o[ORDERS_KEEP].copy(),
            "order_items": it.copy(),
            "order_payments": payments[payments["order_id"].isin(ids)].copy(),
            "customers": customers[customers["customer_id"].isin(o["customer_id"])].copy(),
            "products": products[products["product_id"].isin(it["product_id"])].copy(),
            "sellers": sellers[sellers["seller_id"].isin(it["seller_id"])].copy(),
            "geolocation": geolocation.copy(),
            "product_category_name_translation": categories.copy(),
        }
        labels = o[["order_id", "is_late", "order_delivered_customer_date", "order_delivered_carrier_date"]].rename(
            columns={"order_delivered_customer_date": "delivered_customer_date",
                     "order_delivered_carrier_date": "delivered_carrier_date"}).copy()
        if cfg.data.rekey_ids:
            tables = {k: rekey(v, salt) for k, v in tables.items()}
            labels = rekey(labels, salt)

        split_dir = out / ("train" if split == "train" else "test_features")
        split_dir.mkdir(parents=True)
        for name, df in tables.items():
            df.to_csv(split_dir / f"{name}.csv", index=False)
        if split == "train":
            labels.to_csv(split_dir / "train_labels.csv", index=False)
        else:
            labels[["order_id", "is_late"]].to_csv(out / "test_labels.csv", index=False)

        stats[split] = {
            "orders": len(o),
            "late": int(o["is_late"].sum()),
            "late_rate": round(float(o["is_late"].mean()), 4),
            "purchase_min": str(o["order_purchase_timestamp"].min()),
            "purchase_max": str(o["order_purchase_timestamp"].max()),
            "rows": {k: len(v) for k, v in tables.items()},
        }

    metadata = {
        "prediction_time": "order purchase (order_purchase_timestamp)",
        "label": "is_late = date(order_delivered_customer_date) > order_estimated_delivery_date",
        "population": "orders with status 'delivered' and a delivery date",
        "test_fraction": cfg.data.test_fraction,
        "split_boundary": str(boundary),
        "censor_cutoff": str(cutoff.date()),
        "censor": censor_info,
        "orders_total_delivered": len(delivered),
        "orders_dropped_by_censor_cutoff": len(delivered) - len(kept),
        "ids_rekeyed": cfg.data.rekey_ids,
        "dropped": DROPPED,
        "splits": stats,
        "sha256": {str(p.relative_to(out)): sha256_file(p) for p in sorted(out.rglob("*.csv"))},
    }
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2))
    print(json.dumps({k: v for k, v in metadata.items() if k != "sha256"}, indent=2))


if __name__ == "__main__":
    main()
