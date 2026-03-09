CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyername TEXT NOT NULL,
    sellername TEXT NOT NULL,
    deliverystreet TEXT,
    deliverycity TEXT,
    deliverypostcode TEXT,
    deliverycountry TEXT,
    status TEXT DEFAULT 'pending',
    notes TEXT,
    issueDate TIMESTAMPTZ DEFAULT NOW(),
    lastChanged TIMESTAMPTZ DEFAULT NOW()
);


