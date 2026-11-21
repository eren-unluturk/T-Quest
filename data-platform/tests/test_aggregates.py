import uuid

import pytest

from data_platform import migrate


@pytest.fixture
def conn(db_conn):
    migrate.migrate()
    db_conn.autocommit = True  # refresh_continuous_aggregate cannot run in a transaction
    return db_conn


def _user(conn, override=None):
    uid = uuid.uuid4()
    conn.execute(
        "INSERT INTO users (id, username, home_line_override) VALUES (%s, %s, %s)",
        (uid, f"u-{uid}", override),
    )
    return uid


def _ledger(conn, user, route, days_ago, delta):
    conn.execute(
        "INSERT INTO points_ledger (at, user_id, delta, reason, route_id)"
        " VALUES (now() - make_interval(days => %s), %s, %s, 'checkin', %s)",
        (days_ago, user, delta, route),
    )


def _event(conn, user, route, hours_ago, event_type="checkin", mode="subway", stop="place-pktrm"):
    conn.execute(
        "INSERT INTO rider_events (time, user_id, event_type, route_id, mode, stop_id)"
        " VALUES (now() - make_interval(hours => %s), %s, %s, %s, %s, %s)",
        (hours_ago, user, event_type, route, mode, stop),
    )


def _refresh(conn, *names):
    for name in names:
        conn.execute(f"CALL refresh_continuous_aggregate('{name}', NULL, NULL)")


@pytest.fixture
def ledger_world(conn):
    run = uuid.uuid4().hex[:8]
    r1, r2 = f"T-{run}-1", f"T-{run}-2"
    a, b, c = _user(conn), _user(conn), _user(conn)
    conn.execute("INSERT INTO friends (user_id, friend_id) VALUES (%s, %s)", (a, b))
    _ledger(conn, a, r1, 10, 100)
    _ledger(conn, a, r1, 2, 50)
    _ledger(conn, b, r1, 2, 50)
    _ledger(conn, b, r1, 20, 30)
    _ledger(conn, c, r2, 2, 50)
    _refresh(conn, "leaderboard_daily")
    yield dict(a=a, b=b, c=c, r1=r1, r2=r2)
    conn.execute("DELETE FROM friends WHERE user_id = %s", (a,))
    for u in (a, b, c):
        conn.execute("DELETE FROM users WHERE id = %s", (u,))


def _rows(conn, *args):
    return conn.execute("SELECT position, user_id, points FROM leaderboard(%s, %s, %s, %s)", args).fetchall()


def test_migrate_rerun_is_noop(conn):
    assert migrate.migrate() == []


def test_line_all(conn, ledger_world):
    w = ledger_world
    assert _rows(conn, "line", "all", None, w["r1"]) == [(1, w["a"], 150), (2, w["b"], 80)]


def test_line_week_ties_share_position(conn, ledger_world):
    w = ledger_world
    rows = _rows(conn, "line", "week", None, w["r1"])
    assert {(p, pts) for p, _, pts in rows} == {(1, 50)}
    assert {u for _, u, _ in rows} == {w["a"], w["b"]}


def test_friends_month(conn, ledger_world):
    w = ledger_world
    assert _rows(conn, "friends", "month", w["a"], None) == [(1, w["a"], 150), (2, w["b"], 80)]


def test_global_week_contains_all_three(conn, ledger_world):
    w = ledger_world
    mine = {u: pts for _, u, pts in _rows(conn, "global", "week", None, None) if u in (w["a"], w["b"], w["c"])}
    assert mine == {w["a"]: 50, w["b"]: 50, w["c"]: 50}


def test_home_line_and_affected_users(conn):
    run = uuid.uuid4().hex[:8]
    r1, r2 = f"T-{run}-1", f"T-{run}-2"
    d, e = _user(conn), _user(conn)
    f = _user(conn, override=r2)
    for i in range(6):
        _event(conn, d, r1, i + 1)
    for i in range(3):
        _event(conn, d, r2, i + 1)
    for i in range(4):  # below the 5-ride minimum
        _event(conn, e, r1, i + 1)
    _refresh(conn, "home_line_weekly")
    alert_id = f"test-{run}"
    conn.execute("INSERT INTO alerts (id, effect) VALUES (%s, 'DELAY')", (alert_id,))
    conn.execute("INSERT INTO alert_entities (alert_id, route_id) VALUES (%s, %s)", (alert_id, r1))
    try:
        rows = {
            r[0]: r[1:]
            for r in conn.execute(
                "SELECT user_id, route_id, checkins_28d FROM home_line WHERE user_id = ANY(%s)", ([d, e, f],)
            ).fetchall()
        }
        assert rows[d] == (r1, 6)
        assert e not in rows
        assert rows[f][0] == r2  # override wins
        affected = {r[0] for r in conn.execute("SELECT user_id FROM users_affected_by_alert(%s)", (alert_id,))}
        assert affected == {d}
    finally:
        conn.execute("DELETE FROM alerts WHERE id = %s", (alert_id,))
        for u in (d, e, f):
            conn.execute("DELETE FROM rider_events WHERE user_id = %s", (u,))
            conn.execute("DELETE FROM users WHERE id = %s", (u,))


def test_personal_stats_and_stop_visits(conn):
    u = _user(conn)
    try:
        _event(conn, u, "Red", 1, mode="subway", stop="place-pktrm")
        _event(conn, u, "1", 2, mode="bus", stop="place-harsq")
        _event(conn, u, "Red", 3, mode="subway", stop="place-pktrm")
        _refresh(conn, "personal_stats_daily")
        row = conn.execute(
            "SELECT sum(checkins), sum(bus_events), sum(rail_events) FROM personal_stats_daily WHERE user_id = %s",
            (u,),
        ).fetchone()
        assert row == (3, 1, 2)
        visits = dict(
            conn.execute("SELECT stop_id, visits FROM user_stop_visits WHERE user_id = %s", (u,)).fetchall()
        )
        assert visits == {"place-pktrm": 2, "place-harsq": 1}
    finally:
        conn.execute("DELETE FROM rider_events WHERE user_id = %s", (u,))
        conn.execute("DELETE FROM users WHERE id = %s", (u,))
