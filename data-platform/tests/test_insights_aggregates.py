import uuid

import pytest

from data_platform import migrate


@pytest.fixture
def conn(db_conn):
    migrate.migrate()
    db_conn.autocommit = True  # refresh_continuous_aggregate cannot run in a transaction
    return db_conn


def _checkin(conn, user, stop, route="Red"):
    conn.execute(
        "INSERT INTO rider_events (time, user_id, event_type, stop_id, route_id, mode)"
        " VALUES (now() - interval '2 hours', %s, 'checkin', %s, %s, 'subway')",
        (user, stop, route),
    )


def test_migrate_rerun_is_noop(conn):
    assert migrate.migrate() == []


def test_home_line_has_checkins_28d_column(conn):
    cols = [r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'home_line'"
        " ORDER BY ordinal_position").fetchall()]
    assert cols == ["user_id", "route_id", "checkins_28d"]


def test_stop_popularity_and_user_stop_daily(conn):
    run = uuid.uuid4().hex[:8]
    stop = f"T{run}-stop"
    u1, u2 = uuid.uuid4(), uuid.uuid4()
    try:
        _checkin(conn, u1, stop)
        _checkin(conn, u1, stop)
        _checkin(conn, u2, stop)
        for cagg in ("user_stop_hourly", "user_stop_daily"):
            conn.execute(f"CALL refresh_continuous_aggregate('{cagg}', NULL, NULL)")

        hourly = conn.execute(
            "SELECT sum(checkins), max(unique_users) FROM stop_popularity_hourly WHERE stop_id = %s", (stop,)
        ).fetchone()
        assert hourly == (3, 2)

        daily = dict(conn.execute(
            "SELECT user_id, sum(visits) FROM user_stop_daily WHERE stop_id = %s GROUP BY user_id", (stop,)
        ).fetchall())
        assert daily == {u1: 2, u2: 1}
    finally:
        conn.execute("DELETE FROM rider_events WHERE stop_id = %s", (stop,))
