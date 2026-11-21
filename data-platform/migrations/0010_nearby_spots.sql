-- Nearby spots, categories and verified identity labels (owner: data-platform, requested by insights-sponsors).
-- Label policy: a label is shown only when status is declared or certified, with evidence.
-- Never infer a label from a name, photo, review or menu. Idempotent.

ALTER TABLE sponsors ADD COLUMN IF NOT EXISTS demo_placeholder boolean NOT NULL DEFAULT false;
ALTER TABLE stores   ADD COLUMN IF NOT EXISTS demo_placeholder boolean NOT NULL DEFAULT false;
ALTER TABLE sponsors DROP CONSTRAINT IF EXISTS sponsors_category_check;
ALTER TABLE sponsors ADD CONSTRAINT sponsors_category_check
    CHECK (category IN ('food','clothing','sports','retail','other'));

CREATE TABLE IF NOT EXISTS spot_categories (
    slug         text PRIMARY KEY,
    display_name text NOT NULL,
    sort_order   int NOT NULL DEFAULT 100
);

CREATE TABLE IF NOT EXISTS label_types (
    slug         text PRIMARY KEY,
    display_name text NOT NULL,          -- configurable wording, the team may rename
    description  text,
    sort_order   int NOT NULL DEFAULT 100
);

CREATE TABLE IF NOT EXISTS nearby_spots (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name             text NOT NULL,
    category_slug    text NOT NULL REFERENCES spot_categories (slug),
    address          text,
    lat              double precision,
    lon              double precision,
    demo_placeholder boolean NOT NULL DEFAULT false,
    sponsor_id       uuid REFERENCES sponsors (id),
    placement_type   text NOT NULL DEFAULT 'listed' CHECK (placement_type IN ('sponsored','listed')),
    active           boolean NOT NULL DEFAULT true,
    removed_at       timestamptz,          -- set when a business asks to be removed
    source           text NOT NULL DEFAULT 'manual',
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sponsored_needs_sponsor CHECK (placement_type <> 'sponsored' OR sponsor_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS nearby_spots_category_idx ON nearby_spots (category_slug);

CREATE TABLE IF NOT EXISTS spot_stop_links (
    spot_id    uuid NOT NULL REFERENCES nearby_spots (id) ON DELETE CASCADE,
    stop_id    text NOT NULL REFERENCES stops (id),
    distance_m double precision,
    PRIMARY KEY (spot_id, stop_id)
);
CREATE INDEX IF NOT EXISTS spot_stop_links_stop_idx ON spot_stop_links (stop_id);

CREATE TABLE IF NOT EXISTS spot_labels (
    spot_id          uuid NOT NULL REFERENCES nearby_spots (id) ON DELETE CASCADE,
    label_slug       text NOT NULL REFERENCES label_types (slug),
    status           text NOT NULL CHECK (status IN ('declared','certified','pending')),
    evidence_url     text,
    declaration_note text,
    verified_at      timestamptz,
    verified_by      text,
    PRIMARY KEY (spot_id, label_slug),
    -- declared or certified rows must carry evidence and who verified them
    CONSTRAINT label_evidence_required CHECK (
        status = 'pending'
        OR ((evidence_url IS NOT NULL OR declaration_note IS NOT NULL)
            AND verified_at IS NOT NULL AND verified_by IS NOT NULL)
    )
);

-- The only thing the API reads: pending labels are not in this view.
CREATE OR REPLACE VIEW spot_labels_public AS
    SELECT spot_id, label_slug, status, evidence_url, declaration_note, verified_at, verified_by
    FROM spot_labels WHERE status IN ('declared','certified');

INSERT INTO spot_categories (slug, display_name, sort_order) VALUES
    ('restaurant','Restaurant',10), ('cafe','Cafe',20), ('store','Store',30),
    ('clothing','Clothing',40), ('grocery','Grocery',50), ('bar','Bar',60), ('other','Other',99)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO label_types (slug, display_name, description, sort_order) VALUES
    ('local-independent','Local / independent','Independently owned local business',10),
    ('woman-owned','Woman-owned',NULL,20),
    ('african-american-owned','African American-owned',NULL,30),
    ('latino-owned','Latino-owned',NULL,40),
    ('asian-owned','Asian-owned',NULL,50),
    ('immigrant-owned','Immigrant-owned',NULL,60),
    ('veteran-owned','Veteran-owned',NULL,70),
    ('lgbtq-owned','LGBTQ+-owned',NULL,80),
    ('family-owned','Family-owned',NULL,90)
ON CONFLICT (slug) DO NOTHING;
