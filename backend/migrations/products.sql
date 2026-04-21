CREATE TABLE IF NOT EXISTS products (
    prod_id BIGSERIAL PRIMARY KEY,
    party_id TEXT NOT NULL,
    name TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL DEFAULT 'EA',
    description TEXT,
    category TEXT NOT NULL,
    image_url TEXT,
    is_visible BOOLEAN NOT NULL DEFAULT TRUE,
    release_date TIMESTAMPTZ,
    show_soldout BOOLEAN NOT NULL DEFAULT TRUE,
    available_units DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (party_id) REFERENCES parties(contact_email) ON DELETE CASCADE,
    UNIQUE (party_id, name)
);
