-- Marks every fave written by the local demo as demo data so the reset script can delete exactly those rows.
-- Additive: one column with a default, on an app table (never on MBTA tables). Idempotent.
ALTER TABLE fact_faves ADD COLUMN IF NOT EXISTS is_demo boolean NOT NULL DEFAULT true;
