CREATE TABLE IF NOT EXISTS public.order_gen_xml (
  order_id TEXT UNIQUE,
  buyer_id TEXT,
  seller_id TEXT,
  xml TEXT,
  ublxml TEXT
);

ALTER TABLE public.order_gen_xml
  ADD COLUMN IF NOT EXISTS order_id TEXT,
  ADD COLUMN IF NOT EXISTS buyer_id TEXT,
  ADD COLUMN IF NOT EXISTS seller_id TEXT,
  ADD COLUMN IF NOT EXISTS xml TEXT,
  ADD COLUMN IF NOT EXISTS ublxml TEXT;

UPDATE public.order_gen_xml
SET
  xml = COALESCE(xml, ublxml),
  ublxml = COALESCE(ublxml, xml);

CREATE TABLE IF NOT EXISTS public.invoice_xml (
  order_id TEXT UNIQUE,
  buyer_id TEXT,
  seller_id TEXT,
  xml TEXT,
  ublxml TEXT
);

ALTER TABLE public.invoice_xml
  ADD COLUMN IF NOT EXISTS order_id TEXT,
  ADD COLUMN IF NOT EXISTS buyer_id TEXT,
  ADD COLUMN IF NOT EXISTS seller_id TEXT,
  ADD COLUMN IF NOT EXISTS xml TEXT,
  ADD COLUMN IF NOT EXISTS ublxml TEXT;

UPDATE public.invoice_xml
SET
  xml = COALESCE(xml, ublxml),
  ublxml = COALESCE(ublxml, xml);

CREATE TABLE IF NOT EXISTS public.dispatch_xml (
  order_id TEXT UNIQUE,
  buyer_id TEXT,
  seller_id TEXT,
  xml TEXT,
  ublxml TEXT
);

ALTER TABLE public.dispatch_xml
  ADD COLUMN IF NOT EXISTS order_id TEXT,
  ADD COLUMN IF NOT EXISTS buyer_id TEXT,
  ADD COLUMN IF NOT EXISTS seller_id TEXT,
  ADD COLUMN IF NOT EXISTS xml TEXT,
  ADD COLUMN IF NOT EXISTS ublxml TEXT;

UPDATE public.dispatch_xml
SET
  xml = COALESCE(xml, ublxml),
  ublxml = COALESCE(ublxml, xml);

CREATE TABLE IF NOT EXISTS public.dispatched_xml (
  order_id TEXT UNIQUE,
  buyer_id TEXT,
  seller_id TEXT,
  xml TEXT,
  ublxml TEXT
);

ALTER TABLE public.dispatched_xml
  ADD COLUMN IF NOT EXISTS order_id TEXT,
  ADD COLUMN IF NOT EXISTS buyer_id TEXT,
  ADD COLUMN IF NOT EXISTS seller_id TEXT,
  ADD COLUMN IF NOT EXISTS xml TEXT,
  ADD COLUMN IF NOT EXISTS ublxml TEXT;

UPDATE public.dispatched_xml
SET
  xml = COALESCE(xml, ublxml),
  ublxml = COALESCE(ublxml, xml);
