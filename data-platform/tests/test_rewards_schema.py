import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from data_platform import migrate


@pytest.fixture
def conn(db_conn):
    migrate.migrate()
    db_conn.autocommit = True
    return db_conn


@pytest.fixture
def world(conn):
    """Throwaway user, sponsor, store, offer, badge, physical reward; cleaned up after."""
    u, sp, st, of, rw, pr = (uuid.uuid4() for _ in range(6))
    badge = f"test-{uuid.uuid4().hex[:8]}"
    conn.execute("INSERT INTO users (id, username) VALUES (%s, %s)", (u, f"u-{u}"))
    conn.execute("INSERT INTO sponsors (id, name) VALUES (%s, 'T')", (sp,))
    conn.execute("INSERT INTO stores (id, sponsor_id) VALUES (%s, %s)", (st, sp))
    conn.execute("INSERT INTO offers (id, sponsor_id) VALUES (%s, %s)", (of, sp))
    conn.execute("INSERT INTO rewards (id, title, points_cost) VALUES (%s, 'R', 10)", (rw,))
    conn.execute("INSERT INTO badges (id, name) VALUES (%s, 'B')", (badge,))
    conn.execute(
        "INSERT INTO physical_rewards (id, name, badge_id) VALUES (%s, 'P', %s)", (pr, badge)
    )
    yield dict(user=u, sponsor=sp, store=st, offer=of, reward=rw, phys=pr, badge=badge)
    conn.execute("DELETE FROM redemptions WHERE user_id = %s", (u,))
    conn.execute("DELETE FROM store_inventory WHERE store_id = %s", (st,))
    conn.execute("DELETE FROM physical_rewards WHERE id = %s", (pr,))
    conn.execute("DELETE FROM badges WHERE id = %s", (badge,))
    conn.execute("DELETE FROM rewards WHERE id = %s", (rw,))
    conn.execute("DELETE FROM offers WHERE id = %s", (of,))
    conn.execute("DELETE FROM stores WHERE id = %s", (st,))
    conn.execute("DELETE FROM sponsors WHERE id = %s", (sp,))
    conn.execute("DELETE FROM users WHERE id = %s", (u,))


def _redeem(conn, w, code, offer="offer", reward=None, phys=None, expires=None, status="issued"):
    expires = expires or datetime.now(timezone.utc) + timedelta(hours=24)
    conn.execute(
        "INSERT INTO redemptions (code, user_id, offer_id, reward_id, physical_reward_id,"
        " expires_at, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (code, w["user"], w["offer"] if offer else None, reward, phys, expires, status),
    )


def test_migrate_rerun_is_noop(conn):
    assert migrate.migrate() == []


def test_redemption_requires_exactly_one_target(conn, world):
    with pytest.raises(psycopg.errors.CheckViolation):
        _redeem(conn, world, "ABCDEFGH23", offer=None)  # zero targets
    with pytest.raises(psycopg.errors.CheckViolation):
        _redeem(conn, world, "ABCDEFGH24", reward=world["reward"])  # two targets
    _redeem(conn, world, "ABCDEFGH25")  # one target


@pytest.mark.parametrize("code", ["0BCDEFGH23", "OBCDEFGH23", "1BCDEFGH23", "IBCDEFGH23", "SHORT"])
def test_code_regex_rejects(conn, world, code):
    with pytest.raises(psycopg.errors.CheckViolation):
        _redeem(conn, world, code)


def test_inventory_cannot_go_negative(conn, world):
    conn.execute(
        "INSERT INTO store_inventory (store_id, physical_reward_id, stock) VALUES (%s, %s, 1)",
        (world["store"], world["phys"]),
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "UPDATE store_inventory SET stock = stock - 2 WHERE store_id = %s", (world["store"],)
        )


def test_physical_reward_needs_badge(conn):
    with pytest.raises(psycopg.errors.NotNullViolation):
        conn.execute("INSERT INTO physical_rewards (name) VALUES ('x')")


def test_expire_redemptions_only_past_due_issued(conn, world):
    now = datetime.now(timezone.utc)
    _redeem(conn, world, "PASTDUE223", expires=now - timedelta(hours=1))
    _redeem(conn, world, "FUTURE2233", expires=now + timedelta(hours=1))
    _redeem(conn, world, "CLAIMED223", expires=now - timedelta(hours=1), status="claimed")
    conn.execute("SELECT expire_redemptions()")
    rows = dict(
        conn.execute(
            "SELECT code, status FROM redemptions WHERE user_id = %s", (world["user"],)
        ).fetchall()
    )
    assert rows == {"PASTDUE223": "expired", "FUTURE2233": "issued", "CLAIMED223": "claimed"}
