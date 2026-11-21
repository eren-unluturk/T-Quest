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
def user(conn):
    uid = uuid.uuid4()
    conn.execute("INSERT INTO users (id, username) VALUES (%s, %s)", (uid, f"u-{uid}"))
    yield uid
    conn.execute("DELETE FROM consent WHERE user_id = %s", (uid,))
    conn.execute("DELETE FROM users WHERE id = %s", (uid,))


def test_migrate_rerun_is_noop(conn):
    assert migrate.migrate() == []


def test_hypertables(conn):
    rows = conn.execute(
        "SELECT hypertable_name FROM timescaledb_information.hypertables"
    ).fetchall()
    names = {r[0] for r in rows}
    assert {"rider_events", "points_ledger"} <= names


def test_ledger_is_append_only(conn, user):
    conn.execute(
        "INSERT INTO points_ledger (user_id, delta, reason) VALUES (%s, 10, 'checkin')", (user,)
    )
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("UPDATE points_ledger SET delta = 99 WHERE user_id = %s", (user,))
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("DELETE FROM points_ledger WHERE user_id = %s", (user,))


def test_user_rank_with_redemption(conn, user):
    conn.execute(
        "INSERT INTO points_ledger (user_id, delta, reason) VALUES (%s, 1500, 'checkin')", (user,)
    )
    conn.execute(
        "INSERT INTO points_ledger (user_id, delta, reason) VALUES (%s, -200, 'redemption')", (user,)
    )
    row = conn.execute(
        "SELECT rank, discount_pct, lifetime, balance FROM user_rank WHERE user_id = %s", (user,)
    ).fetchone()
    assert row == (2, 5, 1500, 1300)


def test_consent_unique_and_active_view(conn, user):
    conn.execute("INSERT INTO consent (user_id, scope) VALUES (%s, 'location')", (user,))
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute("INSERT INTO consent (user_id, scope) VALUES (%s, 'location')", (user,))

    active = conn.execute("SELECT count(*) FROM active_consent WHERE user_id = %s", (user,)).fetchone()[0]
    assert active == 1

    conn.execute(
        "UPDATE consent SET revoked_at = now() WHERE user_id = %s AND scope = 'location'", (user,)
    )
    active = conn.execute("SELECT count(*) FROM active_consent WHERE user_id = %s", (user,)).fetchone()[0]
    assert active == 0
    total = conn.execute("SELECT count(*) FROM consent WHERE user_id = %s", (user,)).fetchone()[0]
    assert total == 1
