# Leakage decisions

**Prediction time is the moment of purchase.** A feature is allowed only if it's known when the customer places the order.
The evidence below comes from `python -m data_prep.explore`.

## Label
`is_late = date(order_delivered_customer_date) > order_estimated_delivery_date`.
Estimated dates are always midnight, so the comparison is at day level and same-day delivery counts as on time.
Population: orders with status `delivered` and a non-null delivery date (96,470 of 99,441). The late rate is 6.8% overall.

## Dropped

| Column / table | Evidence | Why |
|---|---|---|
| `order_reviews` (whole table) | mean score 2.27 for late orders vs 4.21 for on-time; 92% of reviews are created after delivery | written after the outcome is known, so it's a direct proxy for the label |
| `orders.order_delivered_customer_date` | — | defines the label. Kept only in `train/train_labels.csv` |
| `orders.order_delivered_carrier_date` | median 53 h after purchase | post-purchase; a late handoff strongly predicts late delivery. Kept only in `train_labels.csv` |
| `orders.order_approved_at` | median 0.3 h but q99 90 h after purchase | post-purchase; payment approval delay is information not yet known at purchase |
| `orders.order_status` | `delivered` / `shipped` / `canceled` … | reflects the outcome. Used only to select delivered orders |
| `order_items.shipping_limit_date` | in 82% of items it equals `order_approved_at` + a whole number of days (only 4% vs purchase time) | derived from approval time, so it encodes post-purchase approval delay |

## Kept
- `orders`: `order_id`, `customer_id`, `order_purchase_timestamp`, `order_estimated_delivery_date`. Olist's data dictionary says the estimate is shown to the customer at purchase.
- `order_items` (minus `shipping_limit_date`), `order_payments`, `customers`, `sellers`, `products`, `geolocation`, `product_category_name_translation`. All are known at purchase or static.
- `customers.customer_unique_id` lets the model link repeat buyers. In test, using a customer's train-period history is legitimate (it's the past).

## Temporal split and right-censoring
- Deliveries stop being recorded around **2018-08-31** (the data snapshot). Late orders arrive a median of 7 days after their estimate, and 90% within **22 days**.
- For orders whose estimate falls near the snapshot, the late ones weren't delivered yet. They show up as `shipped`, get excluded, and push the late rate artificially low. The tail weeks of August show exactly this.
- The `auto` cutoff is the first 2018 purchase day where fewer than 95% of orders have `estimate + 22 days ≤ snapshot`. That day is **2018-07-05**, and 11,693 later orders are dropped.
- The remaining 84,777 orders are sorted by purchase time; the **last 20%** become test.

| Split | Orders | Purchase window | Late rate |
|---|---|---|---|
| train | 67,821 | 2016-09-15 → 2018-04-16 | 7.8% |
| test | 16,956 | 2018-04-16 → 2018-07-04 | 3.8% |

The test window includes the May 2018 truckers' strike, and its late rate is half the train rate. That distribution shift is real and intentional, so PR-AUC on test will look lower than an in-train random CV suggests.

## Anti-memorization
All IDs (`order_id`, `customer_id`, `customer_unique_id`, `product_id`, `seller_id`) are replaced by `sha256(DATA_SALT:column:id)[:16]`. A submitted script can't carry a lookup table built from the public Kaggle dataset. The salt lives only in `.env`.

## Known limitations
- Orders stuck in `shipped` (~1% per month) are excluded rather than labelled late. Some are probably lost or very late shipments.
- Lookup tables (`products`, `sellers`) are restricted per split to referenced rows. A product's or seller's existence in test is therefore visible only through test orders, which is fine because those are known at prediction time.
