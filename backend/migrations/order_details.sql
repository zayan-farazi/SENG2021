CREATE TABLE IF NOT EXISTS orderdetails (
  orderid INTEGER NOT NULL,
  productid BIGINT,
  productname TEXT NOT NULL,
  unitcode TEXT,
  quantity FLOAT NOT NULL,
  unitprice FLOAT,
  FOREIGN KEY (orderid) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (productid) REFERENCES products(prod_id) ON DELETE SET NULL
);
