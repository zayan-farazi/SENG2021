CREATE VIEW orders_with_buyer AS
SELECT 
    o.*,
    p.contact_email AS "buyeremail",
    p.party_name    AS "buyername"
FROM orders o
LEFT JOIN parties p ON p.contact_email = o.buyer_email;