"""Remove every row the game-engine demo wrote to the shared database.

    python -m game_engine.demo_reset --dry-run     (from game-engine/src; counts only)
    GE_ALLOW_DB_WRITES=1 python -m game_engine.demo_reset

Demo rows are the rows of users whose username starts with "demo_" (every user
the service creates), plus their rider_events (is_synthetic = true). It never
touches other users. points_ledger is append-only (trigger), so, like
data_platform.bench --cleanup, the guard is lifted only for this delete, inside
one transaction: if anything fails, everything including the trigger rolls back.
The badges table keeps its slug rows (they are catalog, not demo data).
"""
import os
import sys

from .pg_store import DEMO_PREFIX

TABLES = [  # (label, count/delete sql with %(p)s = demo prefix)
    ("rider_events", "rider_events WHERE user_id IN (SELECT id FROM users WHERE starts_with(username, %(p)s))"),
    ("user_collections", "user_collections WHERE user_id IN (SELECT id FROM users WHERE starts_with(username, %(p)s))"),
    ("friends", "friends WHERE user_id IN (SELECT id FROM users WHERE starts_with(username, %(p)s)) "
                "OR friend_id IN (SELECT id FROM users WHERE starts_with(username, %(p)s))"),
    ("redemptions", "redemptions WHERE user_id IN (SELECT id FROM users WHERE starts_with(username, %(p)s))"),
    ("points_ledger", "points_ledger WHERE user_id IN (SELECT id FROM users WHERE starts_with(username, %(p)s))"),
    ("users", "users WHERE starts_with(username, %(p)s)"),
]


def run(conn, dry_run=False, allow_writes=None):
    """Return {table: rows}. conn must NOT be in autocommit mode when you want one transaction
    (main() takes care of that). Raises if writes are not allowed and this is not a dry run."""
    if allow_writes is None:
        allow_writes = os.environ.get("GE_ALLOW_DB_WRITES") == "1"
    if not dry_run and not allow_writes:
        raise PermissionError("set GE_ALLOW_DB_WRITES=1 to delete demo rows (or use --dry-run)")
    params = {"p": DEMO_PREFIX}
    counts = {}
    for label, where in TABLES:
        counts[label] = conn.execute("SELECT count(*) FROM " + where, params).fetchone()[0]
    if dry_run:
        return counts
    conn.execute("ALTER TABLE points_ledger DISABLE TRIGGER points_ledger_no_mutation")
    for label, where in TABLES:
        conn.execute("DELETE FROM " + where, params)
    conn.execute("ALTER TABLE points_ledger ENABLE TRIGGER points_ledger_no_mutation")
    return counts


def main(argv):
    import psycopg
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=False, connect_timeout=15)
    try:
        counts = run(conn, dry_run="--dry-run" in argv)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    verb = "would remove" if "--dry-run" in argv else "removed"
    print(verb, counts)


if __name__ == "__main__":
    main(sys.argv[1:])
