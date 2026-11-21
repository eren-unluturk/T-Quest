-- Columnar compression for rider_events (Tiger Data demo).
-- The primary key is (id, time), so both must be in the segmentby/orderby set.
-- Idempotent.
ALTER TABLE rider_events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'user_id',
    timescaledb.compress_orderby = 'time DESC, id'
);

SELECT add_compression_policy('rider_events', INTERVAL '7 days', if_not_exists => TRUE);
