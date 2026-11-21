-- Tourist content from open sources, linked to stops. Every row keeps source, license and attribution.
-- Owner: data-platform (requested by insights-sponsors). Idempotent.

CREATE TABLE IF NOT EXISTS content_sources (
    id           text PRIMARY KEY,
    name         text NOT NULL,
    url          text NOT NULL,
    license      text NOT NULL,
    attribution  text NOT NULL,
    commercial_ok boolean NOT NULL,
    notes        text
);

CREATE TABLE IF NOT EXISTS content_items (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id         text NOT NULL REFERENCES content_sources (id),
    external_id       text NOT NULL,
    source_url        text NOT NULL,
    title             text NOT NULL,
    short_description text,
    category          text,
    lat               double precision,
    lon               double precision,
    license           text NOT NULL,
    attribution       text NOT NULL,
    commercial_ok     boolean NOT NULL DEFAULT false,
    retrieved_at      timestamptz NOT NULL DEFAULT now(),
    needs_verify      boolean NOT NULL DEFAULT false,
    UNIQUE (source_id, external_id)
);
CREATE INDEX IF NOT EXISTS content_items_lat_lon_idx ON content_items (lat, lon);

CREATE TABLE IF NOT EXISTS stop_content (
    stop_id    text NOT NULL REFERENCES stops (id),
    content_id uuid NOT NULL REFERENCES content_items (id) ON DELETE CASCADE,
    distance_m double precision NOT NULL,
    PRIMARY KEY (stop_id, content_id)
);
CREATE INDEX IF NOT EXISTS stop_content_content_idx ON stop_content (content_id);

CREATE TABLE IF NOT EXISTS loading_facts (
    id          uuid PRIMARY KEY,
    body        text NOT NULL,
    tags        text[] NOT NULL DEFAULT '{}',
    source_url  text,
    attribution text NOT NULL,
    needs_verify boolean NOT NULL DEFAULT true
);
