import uuid

import psycopg
import pytest

from data_platform import migrate


@pytest.fixture
def conn(db_conn):
    migrate.migrate()
    db_conn.autocommit = True
    return db_conn


@pytest.fixture
def sponsor(conn):
    sid = uuid.uuid4()
    conn.execute("INSERT INTO sponsors (id, name) VALUES (%s, 'T')", (sid,))
    yield sid
    conn.execute("DELETE FROM offers WHERE sponsor_id = %s", (sid,))
    conn.execute("DELETE FROM sponsors WHERE id = %s", (sid,))


def test_migrate_rerun_is_noop(conn):
    assert migrate.migrate() == []


def test_user_without_ledger_rows_is_rank_1(conn):
    uid = uuid.uuid4()
    conn.execute("INSERT INTO users (id, username) VALUES (%s, %s)", (uid, f"u-{uid}"))
    try:
        row = conn.execute(
            "SELECT rank, discount_pct, lifetime, balance FROM user_rank WHERE user_id = %s", (uid,)
        ).fetchone()
        assert row == (1, 3, 0, 0)
    finally:
        conn.execute("DELETE FROM users WHERE id = %s", (uid,))


def test_offers_kind_and_placement_checks(conn, sponsor):
    conn.execute(
        "INSERT INTO offers (sponsor_id, kind, placement) VALUES (%s, 'points_item', 'sponsored_quest')",
        (sponsor,))
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO offers (sponsor_id, kind, placement) VALUES (%s, 'discount', 'popup')", (sponsor,))
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO offers (sponsor_id, kind) VALUES (%s, 'bogus')", (sponsor,))


def test_consent_granted_flips_on_revoke(conn):
    uid = uuid.uuid4()
    conn.execute("INSERT INTO users (id, username) VALUES (%s, %s)", (uid, f"u-{uid}"))
    try:
        conn.execute("INSERT INTO consent (user_id, scope) VALUES (%s, 'place_visits')", (uid,))
        q = "SELECT granted FROM consent WHERE user_id = %s AND scope = 'place_visits'"
        assert conn.execute(q, (uid,)).fetchone()[0] is True
        conn.execute("UPDATE consent SET revoked_at = now() WHERE user_id = %s", (uid,))
        assert conn.execute(q, (uid,)).fetchone()[0] is False
    finally:
        conn.execute("DELETE FROM consent WHERE user_id = %s", (uid,))
        conn.execute("DELETE FROM users WHERE id = %s", (uid,))


def test_place_visits_hypertable_with_retention_job(conn):
    assert conn.execute(
        "SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = 'place_visits'"
    ).fetchone()
    assert conn.execute(
        "SELECT 1 FROM timescaledb_information.jobs"
        " WHERE hypertable_name = 'place_visits' AND proc_name = 'policy_retention'"
    ).fetchone()


def test_new_columns_and_tables_exist(conn):
    cols = {(t, c) for t, c in conn.execute(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'"
    ).fetchall()}
    for expected in [("stops", "mode"), ("stop_facts", "sort"), ("stop_facts", "tags"),
                     ("stores", "category"), ("offers", "required_badge_id"),
                     ("offers", "per_user_limit"), ("offers", "placement"),
                     ("physical_rewards", "description"), ("consent", "granted"),
                     ("freedom_trail_sites", "nearest_stop_id"), ("fun_facts", "tags")]:
        assert expected in cols, expected


def test_stops_mode_backfill_prefers_rail(conn):
    run = uuid.uuid4().hex[:8]
    stop, subway, bus = f"T{run}-s", f"T{run}-sub", f"T{run}-bus"
    conn.execute("INSERT INTO stops (id, name, lat, lon) VALUES (%s, 'x', 10, 10)", (stop,))
    conn.execute("INSERT INTO routes (id, mode) VALUES (%s, 'subway'), (%s, 'bus')", (subway, bus))
    conn.execute("INSERT INTO route_stops (route_id, stop_id, direction_id) VALUES (%s, %s, 0), (%s, %s, 0)",
                 (bus, stop, subway, stop))
    try:
        from data_platform import load_static
        conn.execute(load_static.BACKFILL_STOP_MODE)
        assert conn.execute("SELECT mode FROM stops WHERE id = %s", (stop,)).fetchone()[0] == "subway"
    finally:
        conn.execute("DELETE FROM route_stops WHERE stop_id = %s", (stop,))
        conn.execute("DELETE FROM routes WHERE id = ANY(%s)", ([subway, bus],))
        conn.execute("DELETE FROM stops WHERE id = %s", (stop,))
