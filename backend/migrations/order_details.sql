CREATE TABLE IF NOT EXISTS orderdetails (
  orderid INTEGER NOT NULL,
  productname TEXT NOT NULL,
  unitcode TEXT,
  quantity FLOAT NOT NULL,
  unitprice FLOAT,
  FOREIGN KEY (orderid) REFERENCES orders(id) ON DELETE CASCADE
);
