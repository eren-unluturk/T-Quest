"""Ordered, idempotent SQL migration runner.

Usage: python -m data_platform.migrate

Applies migrations/NNNN_*.sql in lexical order, each in its own transaction,
skipping versions already recorded in schema_migrations. A file whose first
line is `-- migrate:no-transaction` runs in autocommit mode (needed for
continuous aggregates and their policies).
"""
import hashlib
import sys
from pathlib import Path

from . import db

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
NO_TX_MARKER = "-- migrate:no-transaction"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz DEFAULT now(),
    checksum text
)
"""


def _checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def migrate(migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply pending migrations. Returns the list of versions applied."""
    files = sorted(migrations_dir.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    applied: list[str] = []

    with db.connect(autocommit=True) as conn:
        conn.execute(CREATE_TABLE)
        done = dict(conn.execute("SELECT version, checksum FROM schema_migrations").fetchall())

        for path in files:
            version = path.stem
            sql = path.read_text(encoding="utf-8")
            checksum = _checksum(sql)

            if version in done:
                if done[version] and done[version] != checksum:
                    print(f"WARN  {version}: file changed since it was applied", file=sys.stderr)
                continue

            no_tx = sql.lstrip().startswith(NO_TX_MARKER)
            if no_tx:
                conn.execute(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                    (version, checksum),
                )
            else:
                with conn.transaction():
                    conn.execute(sql)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                        (version, checksum),
                    )
            print(f"applied {version}")
            applied.append(version)

    if not applied:
        print("nothing to apply")
    return applied


def main() -> int:
    migrate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
