-- Per-spot demo fun fact (hand-written, our own wording) and faved facts. Owner: data-platform.
ALTER TABLE nearby_spots ADD COLUMN IF NOT EXISTS fun_fact text;

CREATE TABLE IF NOT EXISTS fact_faves (
    user_key   text NOT NULL,          -- dev auth: the bearer token; no FK so it works before real accounts
    fact_id    text NOT NULL,          -- loading_facts.id or content_items.id
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_key, fact_id)
);
