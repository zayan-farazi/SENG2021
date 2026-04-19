CREATE TABLE  IF NOT products (
    party_id TEXT NOT NULL,
    name TEXT NOT NULL,
    price FLOAT NOT NULL,
    unit TEXT NOT NULL DEFAULT "EA",
    prod_description TEXT,
    is_visible BOOLEAN DEFAULT TRUE,
    release_date DATE,
    show_soldout BOOLEAN DEFAULT TRUE,
    available_units FLOAT,
    FOREIGN KEY (party_id) REFERENCES parties(contact_email) ON DELETE CASCADE
)