CREATE TABLE orderDetails (
  orderId INT,
  productName TEXT NOT NULL,
  unitCode TEXT,
  quantity INT NOT NULL,
  unitPrice INT NOT NULL,
  FOREIGN KEY (orderId) REFERENCES orders(id)
);