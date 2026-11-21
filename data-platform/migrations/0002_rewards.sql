-- Rewards: sponsors, stores, offers, rewards, badges, quests, physical rewards,
-- inventory, user collections, redemptions. Idempotent.

CREATE TABLE IF NOT EXISTS sponsors (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text NOT NULL,
    category   text CHECK (category IN ('food','clothing','sports','retail','other')),
    website    text,
    logo_url   text,
    active     boolean DEFAULT true,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stores (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sponsor_id      uuid NOT NULL REFERENCES sponsors (id),
    name            text,
    address         text,
    lat             double precision,
    lon             double precision,
    nearest_stop_id text REFERENCES stops (id),
    store_key_hash  text,   -- hash of the X-Store-Key; never store the raw key
    active          boolean DEFAULT true
);
CREATE INDEX IF NOT EXISTS stores_nearest_stop_idx ON stores (nearest_stop_id);

CREATE TABLE IF NOT EXISTS offers (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sponsor_id    uuid NOT NULL REFERENCES sponsors (id),
    store_id      uuid REFERENCES stores (id),   -- NULL = all stores of the sponsor
    title         text,
    description   text,
    kind          text CHECK (kind IN ('discount','free_item','local_pick')),
    min_rank      int DEFAULT 1,
    points_cost   int DEFAULT 0,
    discount_pct  int,
    max_value_usd numeric(6,2),
    stock         int,                           -- NULL = unlimited
    starts_at     timestamptz,
    ends_at       timestamptz,
    active        boolean DEFAULT true
);

CREATE TABLE IF NOT EXISTS rewards (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sponsor_id  uuid REFERENCES sponsors (id),
    title       text,
    description text,
    kind        text CHECK (kind IN ('merch','ticket','digital','other')),
    points_cost int NOT NULL,
    min_rank    int DEFAULT 1,
    stock       int,
    active      boolean DEFAULT true
);

CREATE TABLE IF NOT EXISTS badges (
    id          text PRIMARY KEY,   -- slug: line-red-complete, freedom-trail, rank-3
    name        text,
    description text,
    kind        text CHECK (kind IN ('line_complete','rank','trail','stop_count','event','sponsor')),
    criteria    jsonb DEFAULT '{}',
    image_url   text
);

CREATE TABLE IF NOT EXISTS quests (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title           text,
    goal            text,
    criteria        jsonb,
    sponsor_id      uuid REFERENCES sponsors (id),
    reward_points   int DEFAULT 0,
    reward_badge_id text REFERENCES badges (id),
    starts_at       timestamptz,
    ends_at         timestamptz,
    active          boolean DEFAULT true
);

CREATE TABLE IF NOT EXISTS physical_rewards (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sponsor_id     uuid REFERENCES sponsors (id),
    name           text,
    item_type      text CHECK (item_type IN ('sticker','patch','pin','other')),
    badge_id       text NOT NULL REFERENCES badges (id),   -- each physical reward maps to a badge
    min_rank       int DEFAULT 1,
    per_user_limit int DEFAULT 1,
    image_url      text,
    active         boolean DEFAULT true
);

CREATE TABLE IF NOT EXISTS store_inventory (
    store_id           uuid NOT NULL REFERENCES stores (id),
    physical_reward_id uuid NOT NULL REFERENCES physical_rewards (id),
    stock              int NOT NULL CHECK (stock >= 0),
    updated_at         timestamptz DEFAULT now(),
    PRIMARY KEY (store_id, physical_reward_id)
);

CREATE TABLE IF NOT EXISTS user_collections (
    user_id    uuid NOT NULL REFERENCES users (id),
    badge_id   text NOT NULL REFERENCES badges (id),
    earned_at  timestamptz DEFAULT now(),
    source     text,   -- checkin, quest, rank
    source_ref text,
    PRIMARY KEY (user_id, badge_id)
);

CREATE TABLE IF NOT EXISTS redemptions (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code               text UNIQUE NOT NULL CHECK (code ~ '^[A-HJ-NP-Z2-9]{10}$'),
    user_id            uuid NOT NULL REFERENCES users (id),
    store_id           uuid REFERENCES stores (id),
    offer_id           uuid REFERENCES offers (id),
    reward_id          uuid REFERENCES rewards (id),
    physical_reward_id uuid REFERENCES physical_rewards (id),
    status             text NOT NULL DEFAULT 'issued' CHECK (status IN ('issued','claimed','expired')),
    points_spent       int DEFAULT 0,
    issued_at          timestamptz DEFAULT now(),
    expires_at         timestamptz NOT NULL,
    claimed_at         timestamptz,
    claimed_store_id   uuid REFERENCES stores (id),
    CONSTRAINT redemptions_one_target CHECK (
        num_nonnulls(offer_id, reward_id, physical_reward_id) = 1
    )
);
CREATE INDEX IF NOT EXISTS redemptions_user_store_idx   ON redemptions (user_id, store_id, issued_at DESC);
CREATE INDEX IF NOT EXISTS redemptions_status_expiry_idx ON redemptions (status, expires_at);

-- Not scheduled here; game-engine may call it or a job is added later.
CREATE OR REPLACE FUNCTION expire_redemptions() RETURNS integer AS $$
DECLARE
    n integer;
BEGIN
    UPDATE redemptions
       SET status = 'expired'
     WHERE status = 'issued' AND expires_at < now();
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$ LANGUAGE plpgsql;
