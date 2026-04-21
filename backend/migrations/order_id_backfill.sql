ALTER TABLE public.orders
  ADD COLUMN IF NOT EXISTS order_id TEXT;

UPDATE public.orders
SET order_id = 'ord_legacy_' || id::text
WHERE id IS NOT NULL
  AND (order_id IS NULL OR btrim(order_id) = '');

CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_order_id
  ON public.orders (order_id);
