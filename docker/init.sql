-- Synthetic data only: codes, not names. Runs once, on first container start.

CREATE TABLE orders (
    order_id      integer PRIMARY KEY,
    customer_code text          NOT NULL,
    product_sku   text          NOT NULL,
    quantity      integer       NOT NULL CHECK (quantity > 0),
    unit_price    numeric(10,2) NOT NULL CHECK (unit_price >= 0),
    created_at    timestamptz   NOT NULL
);

INSERT INTO orders (order_id, customer_code, product_sku, quantity, unit_price, created_at)
SELECT
    n,
    'CUST-' || lpad(((n - 1) % 8 + 1)::text, 4, '0'),
    'SKU-'  || lpad(((n - 1) % 5 + 1)::text, 3, '0'),
    (n % 4) + 1,
    round((5 + (n * 7) % 45)::numeric, 2),
    timestamptz '2026-01-01 09:00:00+00' + (n || ' hours')::interval
FROM generate_series(1, 20) AS n;
