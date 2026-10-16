# Data: Olist orders (Brazilian e-commerce marketplace)

Training data is in `/data/train/`. Each CSV is one table. Tables join on the ID columns.
All IDs are opaque hashes; they join correctly across tables but do not match any public copy of the dataset.

## Prediction setting
- **Unit:** one order.
- **Prediction time: the moment the order is placed (purchased).** At prediction time you know the order, its items, its payment, the customer, the sellers, and the products. You don't know anything that happens afterwards.
- **Target:** `is_late = 1` if the order reached the customer on a later calendar day than `order_estimated_delivery_date` (the date promised to the customer at purchase), else `0`.
- **Population:** orders that were eventually delivered.
- **Training period:** orders purchased 2016-09-15 → 2018-04-16 (67,821 orders, about 7.8% late).
- **Test period:** orders purchased **after** the training period. The test set has the same tables and columns as `/data/train/`, minus `train_labels.csv`.

## Tables

### `orders.csv`: one row per order
| column | description |
|---|---|
| `order_id` | order key |
| `customer_id` | key into `customers.csv` (one customer_id per order) |
| `order_purchase_timestamp` | when the order was placed |
| `order_estimated_delivery_date` | delivery date promised to the customer at purchase (midnight) |

### `order_items.csv`: one row per item in an order
| column | description |
|---|---|
| `order_id`, `order_item_id` | order key, item sequence number within the order (1, 2, …) |
| `product_id`, `seller_id` | keys into `products.csv`, `sellers.csv` |
| `price`, `freight_value` | item price and its share of the freight cost (BRL) |

### `order_payments.csv`: one row per payment method used for an order
`order_id`, `payment_sequential`, `payment_type` (credit_card, boleto, voucher, debit_card, …), `payment_installments`, `payment_value`

### `customers.csv`
`customer_id`, `customer_unique_id` (the same person across orders), `customer_zip_code_prefix`, `customer_city`, `customer_state`

### `sellers.csv`
`seller_id`, `seller_zip_code_prefix`, `seller_city`, `seller_state`

### `products.csv`
`product_id`, `product_category_name` (Portuguese), `product_name_lenght`, `product_description_lenght`, `product_photos_qty`, `product_weight_g`, `product_length_cm`, `product_height_cm`, `product_width_cm` (the misspellings are in the original data)

### `geolocation.csv`: zip-code-prefix → coordinates (several rows per prefix)
`geolocation_zip_code_prefix`, `geolocation_lat`, `geolocation_lng`, `geolocation_city`, `geolocation_state`

### `product_category_name_translation.csv`
`product_category_name`, `product_category_name_english`

### `train_labels.csv`: **training only, not available at test time**
| column | description |
|---|---|
| `order_id` | order key |
| `is_late` | the target |
| `delivered_customer_date` | when the customer received the order (defines `is_late`) |
| `delivered_carrier_date` | when the seller handed the order to the carrier |

The two delivery dates are post-purchase information. You may use them to build training targets (e.g. predicting delivery duration), but they don't exist for test orders.

## Columns removed on purpose
Some columns of the original dataset were removed because they're only known after purchase: order status, payment approval time, carrier and customer delivery dates (moved to `train_labels.csv`), the seller shipping deadline (derived from approval time), and the whole customer reviews table.
