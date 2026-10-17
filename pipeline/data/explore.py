"""Inspect the raw Olist tables to justify leakage and split decisions.

Prints schemas, null rates, timestamp ranges, order status counts, how each
timestamp relates to purchase time, and the right-censoring curve near the
end of the dataset.
"""

import pandas as pd

from pipeline.config import load_config

ORDER_TS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


def section(title: str) -> None:
    print(f"\n{'=' * 80}\n{title}\n{'=' * 80}")


def main() -> None:
    cfg = load_config()
    raw = cfg.data.raw_dir
    tables = {p.stem: pd.read_csv(p) for p in sorted(raw.glob("*.csv"))}

    section("Schemas and null rates")
    for name, df in tables.items():
        print(f"\n{name}  rows={len(df):,}")
        for col in df.columns:
            print(f"  {col:40s} {str(df[col].dtype):10s} null={df[col].isna().mean():6.1%}  nunique={df[col].nunique():,}")

    orders = tables["olist_orders_dataset"].copy()
    for col in ORDER_TS:
        orders[col] = pd.to_datetime(orders[col])
    purchase = orders["order_purchase_timestamp"]

    section("Order status counts")
    print(orders["order_status"].value_counts().to_string())

    section("Timestamp ranges")
    for col in ORDER_TS:
        print(f"  {col:35s} {orders[col].min()}  ->  {orders[col].max()}")

    section("Hours after purchase (quantiles) -- anything > 0 is post-purchase information")
    q = [0.01, 0.25, 0.5, 0.75, 0.99]
    for col in ORDER_TS[1:]:
        hours = (orders[col] - purchase).dt.total_seconds() / 3600
        print(f"  {col:35s} " + "  ".join(f"q{int(x * 100):02d}={hours.quantile(x):8.1f}" for x in q))
    est_time = orders["order_estimated_delivery_date"].dt.time.value_counts()
    print(f"\n  estimated_delivery time-of-day values: {est_time.head(3).to_dict()}")

    items = tables["olist_order_items_dataset"].copy()
    items["shipping_limit_date"] = pd.to_datetime(items["shipping_limit_date"])
    items = items.merge(orders[["order_id", "order_purchase_timestamp", "order_approved_at"]], on="order_id")
    d_purchase = (items["shipping_limit_date"] - items["order_purchase_timestamp"]).dt.total_seconds() / 86400
    d_approved = (items["shipping_limit_date"] - items["order_approved_at"]).dt.total_seconds() / 86400
    section("order_items.shipping_limit_date relative to purchase / approval (days)")
    print("  vs purchase:", d_purchase.describe(percentiles=[0.01, 0.5, 0.99]).round(2).to_dict())
    print("  vs approved:", d_approved.describe(percentiles=[0.01, 0.5, 0.99]).round(2).to_dict())
    print(f"  share > 30 days after purchase: {(d_purchase > 30).mean():.2%}")

    payments = tables["olist_order_payments_dataset"]
    section("Payments")
    print(payments["payment_type"].value_counts().to_string())
    print("  payment_sequential max:", payments["payment_sequential"].max())

    reviews = tables["olist_order_reviews_dataset"].copy()
    reviews["review_creation_date"] = pd.to_datetime(reviews["review_creation_date"])
    rv = reviews.merge(orders[["order_id", "order_delivered_customer_date", "order_estimated_delivery_date"]], on="order_id")
    rv["late"] = rv["order_delivered_customer_date"].dt.normalize() > rv["order_estimated_delivery_date"].dt.normalize()
    section("Reviews vs lateness (confirms reviews leak the label)")
    print(rv.groupby("late")["review_score"].agg(["mean", "count"]).to_string())
    print(f"  review created before delivery: {(rv['review_creation_date'] < rv['order_delivered_customer_date']).mean():.1%}")

    section("Label: delivered orders, late = delivered date > estimated date")
    delivered = orders[(orders["order_status"] == "delivered") & orders["order_delivered_customer_date"].notna()].copy()
    delivered["is_late"] = (
        delivered["order_delivered_customer_date"].dt.normalize() > delivered["order_estimated_delivery_date"].dt.normalize()
    )
    print(f"  delivered with date: {len(delivered):,}   late rate: {delivered['is_late'].mean():.2%}")
    print(f"  status=delivered but no delivered date: {((orders['order_status'] == 'delivered') & orders['order_delivered_customer_date'].isna()).sum()}")
    print(f"  delivered date present but status != delivered: {((orders['order_status'] != 'delivered') & orders['order_delivered_customer_date'].notna()).sum()}")

    section("Right-censoring: by purchase month, orders / share delivered / late rate among delivered")
    orders["month"] = purchase.dt.to_period("M")
    orders["delivered"] = (orders["order_status"] == "delivered") & orders["order_delivered_customer_date"].notna()
    delivered["month"] = delivered["order_purchase_timestamp"].dt.to_period("M")
    monthly = pd.DataFrame({
        "orders": orders.groupby("month").size(),
        "delivered_share": orders.groupby("month")["delivered"].mean().round(3),
        "late_rate": delivered.groupby("month")["is_late"].mean().round(3),
    })
    print(monthly.to_string())

    section("Last 12 weeks: orders / delivered share / late rate")
    orders["week"] = purchase.dt.to_period("W")
    delivered["week"] = delivered["order_purchase_timestamp"].dt.to_period("W")
    weekly = pd.DataFrame({
        "orders": orders.groupby("week").size(),
        "delivered_share": orders.groupby("week")["delivered"].mean().round(3),
        "late_rate": delivered.groupby("week")["is_late"].mean().round(3),
    })
    print(weekly.tail(12).to_string())

    section("Customers: repeat buyers")
    cust = tables["olist_customers_dataset"]
    per_unique = cust.groupby("customer_unique_id").size()
    print(f"  customer_id rows={len(cust):,} unique people={len(per_unique):,} repeat={(per_unique > 1).sum():,}")
    print(f"  customer_id 1:1 with orders: {orders['customer_id'].is_unique}")


if __name__ == "__main__":
    main()
