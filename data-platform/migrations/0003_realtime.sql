-- MBTA realtime: vehicles and predictions hypertables (compressed, with retention),
-- alerts and alert_entities, active_alerts view. Idempotent.

CREATE TABLE IF NOT EXISTS vehicles (
    time           timestamptz NOT NULL,   -- poll time
    vehicle_id     text NOT NULL,
    route_id       text,
    trip_id        text,
    stop_id        text,
    direction_id   smallint,
    current_status text,
    lat            double precision,
    lon            double precision,
    bearing        real,
    speed          real,
    label          text,
    updated_at     timestamptz             -- from MBTA
);
SELECT create_hypertable('vehicles', 'time',
    chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE UNIQUE INDEX IF NOT EXISTS vehicles_vehicle_time_uq ON vehicles (vehicle_id, time);
CREATE INDEX IF NOT EXISTS vehicles_stop_time_idx  ON vehicles (stop_id, time DESC);
CREATE INDEX IF NOT EXISTS vehicles_route_time_idx ON vehicles (route_id, time DESC);

CREATE TABLE IF NOT EXISTS predictions (
    time                  timestamptz NOT NULL,   -- poll time
    prediction_id         text NOT NULL,
    stop_id               text,
    route_id              text,
    trip_id               text,
    direction_id          smallint,
    arrival_time          timestamptz,
    departure_time        timestamptz,
    status                text,
    schedule_relationship text
);
SELECT create_hypertable('predictions', 'time',
    chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE UNIQUE INDEX IF NOT EXISTS predictions_pred_time_uq ON predictions (prediction_id, time);
CREATE INDEX IF NOT EXISTS predictions_stop_time_idx ON predictions (stop_id, time DESC);

-- TimescaleDB only allows compression on a table with a unique index when every column of
-- that index is a segmentby or orderby column. The unique index is (vehicle_id, time), so
-- vehicle_id goes into orderby next to time. The unique index is kept: ingestion relies on
-- it (ON CONFLICT DO NOTHING) to avoid duplicate samples.
ALTER TABLE vehicles SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'route_id',
    timescaledb.compress_orderby = 'vehicle_id, time DESC'
);
-- Same rule: the unique index is (prediction_id, time), so prediction_id is in orderby.
ALTER TABLE predictions SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'route_id',
    timescaledb.compress_orderby = 'prediction_id, time DESC'
);

SELECT add_compression_policy('vehicles',    INTERVAL '1 day',  if_not_exists => TRUE);
SELECT add_compression_policy('predictions', INTERVAL '1 day',  if_not_exists => TRUE);
SELECT add_retention_policy('vehicles',      INTERVAL '30 days', if_not_exists => TRUE);
SELECT add_retention_policy('predictions',   INTERVAL '30 days', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS alerts (
    id            text PRIMARY KEY,
    effect        text,
    cause         text,
    severity      int,
    header        text,
    description   text,
    lifecycle     text,
    active_start  timestamptz,
    active_end    timestamptz,
    first_seen_at timestamptz DEFAULT now(),
    last_seen_at  timestamptz DEFAULT now(),
    raw           jsonb
);

CREATE TABLE IF NOT EXISTS alert_entities (
    alert_id     text NOT NULL REFERENCES alerts (id) ON DELETE CASCADE,
    route_id     text,
    stop_id      text,
    route_type   int,
    direction_id smallint
);
CREATE INDEX IF NOT EXISTS alert_entities_alert_idx ON alert_entities (alert_id);
CREATE INDEX IF NOT EXISTS alert_entities_route_idx ON alert_entities (route_id);
CREATE INDEX IF NOT EXISTS alert_entities_stop_idx  ON alert_entities (stop_id);

-- Alerts whose active window contains now(). A null start counts as already started.
CREATE OR REPLACE VIEW active_alerts AS
    SELECT *
    FROM alerts
    WHERE (active_start IS NULL OR active_start <= now())
      AND (active_end IS NULL OR active_end > now());
