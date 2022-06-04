CREATE TABLE participant
(
    id         SERIAL PRIMARY KEY,
    name       VARCHAR NOT NULL,
    username   VARCHAR,
    user_total NUMERIC DEFAULT 0
);
CREATE TABLE orders
(
    order_id  SERIAL PRIMARY KEY,
    name      VARCHAR,
    total     NUMERIC CHECK (total >= 0),
    price     NUMERIC CHECK (price >= 0),
    tip       NUMERIC CHECK (tip >= 0),
    timestamp DATE
);
CREATE TABLE cuts
(
    order_id  INT REFERENCES orders (order_id),
    id        INT REFERENCES participant (id),
    cut       NUMERIC NOT NULL,
    timestamp DATE
);
