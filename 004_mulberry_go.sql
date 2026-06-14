-- MulberryGO: sistem rezervări service auto
-- Rulează în Supabase SQL Editor sau PostgreSQL

CREATE TABLE IF NOT EXISTS partners (
  id          UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
  email       TEXT    NOT NULL UNIQUE,
  name        TEXT    NOT NULL,
  cif         TEXT    NOT NULL,
  city        TEXT    NOT NULL DEFAULT '',
  address     TEXT    NOT NULL DEFAULT '',
  phone       TEXT    NOT NULL DEFAULT '',
  description TEXT    NOT NULL DEFAULT '',
  api_token   UUID    DEFAULT gen_random_uuid() UNIQUE NOT NULL,
  active      BOOLEAN DEFAULT TRUE,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS partner_services (
  id           UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
  partner_id   UUID    NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
  name         TEXT    NOT NULL,
  description  TEXT    NOT NULL DEFAULT '',
  duration_min INTEGER NOT NULL DEFAULT 60,
  price_ron    NUMERIC(10,2),
  active       BOOLEAN DEFAULT TRUE,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rezervari (
  id                   UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
  client_email         TEXT    NOT NULL,
  client_vehicle_plate TEXT    NOT NULL DEFAULT '',
  partner_id           UUID    NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
  service_id           UUID    REFERENCES partner_services(id) ON DELETE SET NULL,
  data_programata      TIMESTAMPTZ NOT NULL,
  status               TEXT    NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','confirmed','cancelled','completed')),
  notes                TEXT    NOT NULL DEFAULT '',
  created_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_partner_services_partner ON partner_services(partner_id);
CREATE INDEX IF NOT EXISTS idx_rezervari_partner        ON rezervari(partner_id);
CREATE INDEX IF NOT EXISTS idx_rezervari_client         ON rezervari(client_email);
CREATE INDEX IF NOT EXISTS idx_partners_token           ON partners(api_token);
CREATE INDEX IF NOT EXISTS idx_partners_email           ON partners(email);
