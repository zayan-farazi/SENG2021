DROP VIEW IF EXISTS public.orders_with_buyer;

CREATE VIEW public.orders_with_buyer AS
SELECT
    o.*,
    p.contact_email AS buyeremail_view,
    p.party_name AS buyername_view
FROM public.orders o
LEFT JOIN public.parties p
    ON p.contact_email = COALESCE(o.buyer_id, o.buyeremail);
