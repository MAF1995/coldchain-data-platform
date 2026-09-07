CREATE SCHEMA IF NOT EXISTS quality;

CREATE TABLE quality.product (
    product_code TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    temp_min_c NUMERIC(5,2) NOT NULL,
    temp_max_c NUMERIC(5,2) NOT NULL,
    CHECK (temp_min_c < temp_max_c)
);

CREATE TABLE quality.batch (
    batch_id TEXT PRIMARY KEY,
    product_code TEXT NOT NULL REFERENCES quality.product(product_code),
    expiry_date DATE NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE quality.sensor_event (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_time TIMESTAMPTZ NOT NULL,
    sensor_id TEXT NOT NULL,
    batch_id TEXT NOT NULL REFERENCES quality.batch(batch_id),
    temperature_c NUMERIC(5,2) NOT NULL,
    humidity_pct NUMERIC(5,2),
    battery_pct NUMERIC(5,2),
    raw_hash TEXT NOT NULL UNIQUE
);

