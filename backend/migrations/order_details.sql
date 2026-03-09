CREATE TABLE orderDetails (
  orderId INT,
  productName TEXT NOT NULL,
  unitCode TEXT,
  quantity FLOAT NOT NULL,
  unitPrice FLOAT NOT NULL,
  FOREIGN KEY (orderId) REFERENCES orders(id)
);