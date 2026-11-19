-- ═══════════════════════════════════════════════════════════════════
--  Beat 1 — Create the schema
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE categories (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    description TEXT
);

CREATE TABLE products (
    id          INTEGER PRIMARY KEY,
    category_id INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    price       REAL    NOT NULL,
    stock       INTEGER NOT NULL,
    active      BOOLEAN NOT NULL
);

CREATE TABLE customers (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    city       TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    status      TEXT    NOT NULL,
    total       REAL    NOT NULL,
    created_at  TEXT    NOT NULL
);

CREATE TABLE order_items (
    id         INTEGER PRIMARY KEY,
    order_id   INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity   INTEGER NOT NULL,
    unit_price REAL    NOT NULL
);

CREATE TABLE reviews (
    id          INTEGER PRIMARY KEY,
    product_id  INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    rating      INTEGER NOT NULL,
    comment     TEXT
);

-- ═══════════════════════════════════════════════════════════════════
--  Beat 2 — Load seed data
-- ═══════════════════════════════════════════════════════════════════

INSERT INTO categories VALUES
    (1, 'Electronics', 'Phones, computers, accessories'),
    (2, 'Books',       'Printed and e-books'),
    (3, 'Clothing',    'Apparel and accessories');

INSERT INTO products VALUES
    (1, 1, 'Wireless Mouse',            25.99, 150, TRUE),
    (2, 1, 'Mechanical Keyboard',       89.50,  60, TRUE),
    (3, 1, 'USB-C Hub',                 39.99,   0, TRUE),
    (4, 2, 'Clean Code',                42.00,  30, TRUE),
    (5, 2, 'The Pragmatic Programmer',  49.95,  22, TRUE),
    (6, 3, 'Cotton T-Shirt',            15.00, 200, TRUE),
    (7, 3, 'Denim Jacket',              79.00,  12, FALSE),
    (8, 3, 'Wool Beanie',               18.50,  45, TRUE);

INSERT INTO customers VALUES
    (1, 'Alice Johnson', 'alice@example.com', 'New York',    '2023-11-01'),
    (2, 'Bob Smith',     'bob@example.com',   'Los Angeles', '2023-12-15'),
    (3, 'Carol White',   'carol@example.com', 'Chicago',     '2024-01-20'),
    (4, 'Dave Brown',    'dave@example.com',  'Houston',     '2024-02-01');

INSERT INTO orders VALUES
    (1001, 1, 'delivered', 116.97, '2024-01-15'),
    (1002, 1, 'delivered',  42.00, '2024-02-02'),
    (1003, 2, 'pending',    89.50, '2024-02-10'),
    (1004, 3, 'cancelled',  79.00, '2024-02-11'),
    (1005, 4, 'shipped',    62.45, '2024-02-12');

INSERT INTO order_items VALUES
    (1, 1001, 1, 2, 25.99),
    (2, 1001, 3, 1, 39.99),
    (3, 1001, 8, 2, 12.50),
    (4, 1002, 4, 1, 42.00),
    (5, 1003, 2, 1, 89.50),
    (6, 1004, 7, 1, 79.00),
    (7, 1005, 5, 1, 49.95),
    (8, 1005, 8, 1, 12.50);

INSERT INTO reviews VALUES
    (1, 1, 1, 5, 'Great mouse, very responsive.'),
    (2, 2, 2, 4, 'Nice keys but a bit loud.'),
    (3, 4, 1, 5, 'A must-read for every developer.'),
    (4, 1, 3, 3, 'OK, but the plastic feels cheap.');

-- ═══════════════════════════════════════════════════════════════════
--  Beat 3 — Query: SELECT, WHERE, ORDER BY, LIMIT
-- ═══════════════════════════════════════════════════════════════════

SELECT id, name, price FROM products
    WHERE price > 20 AND active = TRUE
    ORDER BY price DESC LIMIT 4;

SELECT id, name, city FROM customers
    WHERE city = 'New York' OR city = 'Chicago';

SELECT id, status, total FROM orders
    WHERE total > 50 AND status = 'delivered';

-- ═══════════════════════════════════════════════════════════════════
--  Beat 4 — Constraints: PK, NOT NULL, type coercion
-- ═══════════════════════════════════════════════════════════════════

INSERT INTO customers VALUES
    (1, 'Imposter', 'x@x.x', NULL, '2024-01-01');

INSERT INTO products VALUES
    (99, 1, NULL, 9.99, 5, TRUE);

INSERT INTO products VALUES
    (99, 1, 'Fake', 'not-a-price', 5, TRUE);

INSERT INTO products VALUES
    (99, 3, 'Test Item', '19.99', 5, TRUE);

-- ═══════════════════════════════════════════════════════════════════
--  Beat 5 — Modify: UPDATE, DELETE
-- ═══════════════════════════════════════════════════════════════════

UPDATE products SET stock = 0 WHERE id = 7;

UPDATE products SET active = FALSE WHERE category_id = 3;

SELECT id, name, active FROM products ORDER BY id;

DELETE FROM reviews WHERE rating < 4;

SELECT id, product_id, rating FROM reviews;

-- ═══════════════════════════════════════════════════════════════════
--  Beat 6 — Report (client-side aggregates in Python via SELECT)
-- ═══════════════════════════════════════════════════════════════════

SELECT * FROM orders WHERE status = 'delivered';

SELECT order_id, product_id, quantity FROM order_items
    WHERE order_id = 1001;

SELECT id, name, price FROM products ORDER BY price DESC;

-- ═══════════════════════════════════════════════════════════════════
--  Beat 7 — Persistence (you'll quit + reopen — no SQL here)
-- ═══════════════════════════════════════════════════════════════════

SELECT * FROM products ORDER BY id;