CREATE TABLE participant
(
    id         SERIAL PRIMARY KEY,
    name       VARCHAR NOT NULL,
    username   VARCHAR,
    user_total MONEY DEFAULT 0
);
CREATE TABLE orders
(
    order_id  SERIAL PRIMARY KEY,
    name      VARCHAR,
    total     MONEY CHECK (total >= 0),
    price     MONEY CHECK (price >= 0),
    tip       MONEY CHECK (tip >= 0),
    timestamp DATE

);
CREATE TABLE cuts
(
    order_id  INT REFERENCES orders (order_id),
    id        INT REFERENCES participant (id),
    cut       MONEY NOT NULL,
    timestamp DATE
);
