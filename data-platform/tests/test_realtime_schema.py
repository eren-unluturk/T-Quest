import uuid
from datetime import datetime, timedelta, timezone

import pytest

from data_platform import bench, migrate


@pytest.fixture
def conn(db_conn):
    migrate.migrate()
    db_conn.autocommit = True
    return db_conn


def test_migrate_rerun_is_noop(conn):
    assert migrate.migrate() == []


def test_policy_jobs_exist(conn):
    rows = conn.execute(
        "SELECT hypertable_name, proc_name FROM timescaledb_information.jobs"
        " WHERE hypertable_name IN ('vehicles', 'predictions')"
    ).fetchall()
    found = set(rows)
    for table in ("vehicles", "predictions"):
        assert (table, "policy_compression") in found
        assert (table, "policy_retention") in found


def test_old_chunk_compresses_with_ratio_above_one(conn):
    base = datetime.now(timezone.utc) - timedelta(days=2)
    run = uuid.uuid4().hex[:8]
    conn.execute(
        "INSERT INTO vehicles (time, vehicle_id, route_id, stop_id, lat, lon, current_status)"
        " SELECT %s::timestamptz + (g * interval '1 second'),"
        "        'v-' || %s || '-' || (g % 20), 'Red', 'place-pktrm',"
        "        42.35 + (g % 100) / 10000.0, -71.06 - (g % 100) / 10000.0, 'IN_TRANSIT_TO'"
        " FROM generate_series(1, 5000) g",
        (base, run),
    )
    jobs = conn.execute(
        "SELECT job_id FROM timescaledb_information.jobs"
        " WHERE hypertable_name = 'vehicles' AND proc_name = 'policy_compression'"
    ).fetchall()
    for (job_id,) in jobs:
        conn.execute("CALL run_job(%s)", (job_id,))
    stats = bench.compression_stats(("vehicles",))["vehicles"]
    assert stats["ratio"] is not None and stats["ratio"] > 1


def test_active_alerts_excludes_expired(conn):
    now = datetime.now(timezone.utc)
    ids = {k: f"test-{k}-{uuid.uuid4().hex[:8]}" for k in ("live", "expired", "future", "open")}
    rows = [
        (ids["live"], now - timedelta(hours=1), now + timedelta(hours=1)),
        (ids["expired"], now - timedelta(days=2), now - timedelta(days=1)),
        (ids["future"], now + timedelta(days=1), now + timedelta(days=2)),
        (ids["open"], now - timedelta(hours=1), None),
    ]
    for aid, start, end in rows:
        conn.execute(
            "INSERT INTO alerts (id, active_start, active_end) VALUES (%s, %s, %s)", (aid, start, end)
        )
    try:
        active = {
            r[0]
            for r in conn.execute(
                "SELECT id FROM active_alerts WHERE id = ANY(%s)", (list(ids.values()),)
            ).fetchall()
        }
        assert active == {ids["live"], ids["open"]}
    finally:
        conn.execute("DELETE FROM alerts WHERE id = ANY(%s)", (list(ids.values()),))


# ------------------------------------------------ compression vs unique indexes
import re
from pathlib import Path

MIGRATION_0003 = Path(__file__).resolve().parents[1] / "migrations" / "0003_realtime.sql"


def _cols(csv: str) -> set[str]:
    return {re.sub(r"\s+(ASC|DESC)\b.*$", "", c.strip(), flags=re.I) for c in csv.split(",") if c.strip()}


def test_0003_unique_index_columns_are_in_compression_settings():
    """TimescaleDB rejects compression when a unique-index column is neither segmentby nor orderby."""
    sql = MIGRATION_0003.read_text(encoding="utf-8")
    unique = {}
    for table, cols in re.findall(r"CREATE UNIQUE INDEX[^;]*?\bON\s+(\w+)\s*\(([^)]*)\)", sql, flags=re.I):
        unique.setdefault(table, set()).update(_cols(cols))
    compressed = {}
    for table, body in re.findall(r"ALTER TABLE\s+(\w+)\s+SET\s*\((.*?)\);", sql, flags=re.S | re.I):
        seg = re.search(r"compress_segmentby\s*=\s*'([^']*)'", body)
        order = re.search(r"compress_orderby\s*=\s*'([^']*)'", body)
        compressed[table] = _cols(seg.group(1) if seg else "") | _cols(order.group(1) if order else "")

    assert set(unique) == {"vehicles", "predictions"} == set(compressed)
    for table, cols in unique.items():
        missing = cols - compressed[table]
        assert not missing, f"{table}: unique index columns {missing} not in segmentby/orderby"


def test_compression_settings_list_id_columns_as_orderby(conn):
    rows = conn.execute(
        "SELECT hypertable_name, attname FROM timescaledb_information.compression_settings"
        " WHERE hypertable_name IN ('vehicles', 'predictions') AND orderby_column_index IS NOT NULL"
    ).fetchall()
    assert ("vehicles", "vehicle_id") in rows
    assert ("predictions", "prediction_id") in rows
