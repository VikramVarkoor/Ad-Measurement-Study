-- Part B: Olist e-commerce metric layer.
-- Source tables (loaded by src/ecommerce.py): orders, items, payments, reviews,
-- customers, sellers, products, category_translation.
--
-- Join rules learned the hard way (and tested in join_trap_check):
--   * one order has MANY items and possibly SEVERAL payments: joining items to
--     payments on order_id multiplies rows and inflates revenue.
--   * revenue (GMV) is computed from the ITEMS table alone: SUM(price).
--   * an order can carry more than one review (547 do): review score is
--     averaged per order BEFORE any join, so no order is double-counted.

-- ------------------------------------------------------------ order_facts
-- One row per DELIVERED order with its revenue, delivery timing and review.
CREATE OR REPLACE VIEW order_facts AS
WITH order_revenue AS (           -- items table alone: price and freight sums
    SELECT order_id,
           SUM(price)         AS revenue,
           SUM(freight_value) AS freight,
           COUNT(*)           AS items
    FROM items
    GROUP BY order_id
),
order_review AS (                 -- average per order BEFORE joining
    SELECT order_id, AVG(review_score) AS review_score
    FROM reviews
    GROUP BY order_id
)
SELECT
    o.order_id,
    o.customer_id,
    CAST(date_trunc('week', o.order_purchase_timestamp) AS DATE) AS purchase_week,
    r.revenue,
    r.freight,
    r.items,
    v.review_score,
    date_diff('day', o.order_purchase_timestamp, o.order_delivered_customer_date)
        AS delivery_days,
    date_diff('day', o.order_estimated_delivery_date, o.order_delivered_customer_date)
        AS days_late,                       -- positive = later than promised
    (o.order_delivered_customer_date > o.order_estimated_delivery_date) AS is_late
FROM orders o
JOIN order_revenue r USING (order_id)
LEFT JOIN order_review v USING (order_id)
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL;

-- ------------------------------------------------------- join_trap_check
-- The classic error, made measurable: order count must survive every join,
-- and items x payments revenue must EXCEED the honest items-only revenue.
CREATE OR REPLACE VIEW join_trap_check AS
WITH honest AS (
    SELECT COUNT(DISTINCT order_id) AS orders, SUM(price) AS revenue FROM items
),
multiplied AS (
    SELECT COUNT(*) AS rows_after_join, SUM(i.price) AS inflated_revenue
    FROM items i JOIN payments p USING (order_id)
)
SELECT h.orders                   AS orders_in_items,
       (SELECT COUNT(*) FROM order_facts) AS orders_in_order_facts,
       h.revenue                  AS honest_revenue,
       m.rows_after_join,
       m.inflated_revenue,
       m.inflated_revenue / h.revenue AS inflation_factor
FROM honest h, multiplied m;

-- ------------------------------------------------------------ weekly_ecom
-- The monitor feed: one row per purchase week.
CREATE OR REPLACE VIEW weekly_ecom AS
SELECT
    purchase_week,
    COUNT(*)                                   AS orders,
    SUM(revenue)                               AS gmv,
    SUM(revenue) / COUNT(*)                    AS aov,
    AVG(CASE WHEN is_late THEN 1.0 ELSE 0.0 END) AS late_share,
    AVG(delivery_days)                         AS avg_delivery_days,
    AVG(review_score)                          AS avg_review_score
FROM order_facts
GROUP BY purchase_week
ORDER BY purchase_week;

-- -------------------------------------------------------- week_over_week
-- Change against the previous week. SQL skill: LAG().
CREATE OR REPLACE VIEW week_over_week AS
SELECT
    purchase_week,
    orders,
    orders - LAG(orders) OVER w                AS orders_wow,
    gmv,
    gmv - LAG(gmv) OVER w                      AS gmv_wow,
    late_share,
    late_share - LAG(late_share) OVER w        AS late_share_wow,
    avg_review_score,
    avg_review_score - LAG(avg_review_score) OVER w AS review_wow
FROM weekly_ecom
WINDOW w AS (ORDER BY purchase_week);

-- ------------------------------------------------------- delay_vs_review
-- Review score distribution by delivery-delay bucket. CASE buckets.
CREATE OR REPLACE VIEW delay_vs_review AS
SELECT
    CASE
        WHEN days_late <= 0 THEN '1. on time'
        WHEN days_late <= 3 THEN '2. 1-3 days late'
        ELSE '3. >3 days late'
    END                                          AS delay_bucket,
    COUNT(*)                                     AS orders,
    AVG(review_score)                            AS avg_review_score,
    AVG(CASE WHEN review_score <= 2 THEN 1.0 ELSE 0.0 END) AS share_1_2_star
FROM order_facts
WHERE review_score IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- ------------------------------------------------------ late_by_seller_state
-- Where the late deliveries sit (feeds the recommendation table).
CREATE OR REPLACE VIEW late_by_seller_state AS
WITH order_seller AS (            -- an order may span sellers; count each pair once
    SELECT DISTINCT i.order_id, s.seller_state
    FROM items i JOIN sellers s USING (seller_id)
)
SELECT
    s.seller_state,
    COUNT(*)                                     AS orders,
    AVG(CASE WHEN f.is_late THEN 1.0 ELSE 0.0 END) AS late_share,
    AVG(f.review_score)                          AS avg_review_score
FROM order_facts f
JOIN order_seller s USING (order_id)
GROUP BY s.seller_state
HAVING COUNT(*) >= 500                            -- too few orders to trust below this
ORDER BY late_share DESC;
