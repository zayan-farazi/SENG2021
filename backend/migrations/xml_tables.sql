CREATE TABLE IF NOT EXISTS order_gen_xml (
    buyer_id TEXT NOT NULL,
    seller_id TEXT NOT NULL,
    order_id TEXT UNIQUE,
    ublxml TEXT
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS invoice_xml (
    buyer_id TEXT NOT NULL,
    seller_id TEXT NOT NULL,
    order_id TEXT UNIQUE,
    ublxml TEXT
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS dispatch_xml (
    buyer_id TEXT NOT NULL,
    seller_id TEXT NOT NULL,
    order_id TEXT UNIQUE,
    ublxml TEXT
    FOREIGN KEY (order_id) REFERENCES orders(id)
);