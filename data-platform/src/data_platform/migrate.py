"""Ordered, idempotent SQL migration runner.

Usage: python -m data_platform.migrate

Applies migrations/NNNN_*.sql in lexical order, each in its own transaction,
skipping versions already recorded in schema_migrations. A file whose first
line is `-- migrate:no-transaction` runs in autocommit mode (needed for
continuous aggregates and their policies).
"""
import hashlib
import re
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


def split_statements(sql: str) -> list[str]:
    """Split a SQL script into statements on top-level semicolons.

    Aware of -- comments, /* */ comments, '...' strings, "..." identifiers and
    $tag$ ... $tag$ dollar quoting. Needed because a multi-statement string sent
    in one call runs in an implicit transaction, which continuous aggregates reject.
    """
    out: list[str] = []
    buf: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if sql.startswith("--", i):
            j = sql.find(chr(10), i)
            j = n if j == -1 else j
            buf.append(sql[i:j])
            i = j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            j = n if j == -1 else j + 2
            buf.append(sql[i:j])
            i = j
        elif c in ("'", '"'):
            j = i + 1
            while j < n:
                if sql[j] == c:
                    if j + 1 < n and sql[j + 1] == c:
                        j += 2
                        continue
                    break
                j += 1
            buf.append(sql[i:j + 1])
            i = j + 1
        elif c == "$":
            m = re.match(r"\$([A-Za-z_][A-Za-z0-9_]*)?\$", sql[i:])
            if m:
                tag = m.group(0)
                j = sql.find(tag, i + len(tag))
                j = n if j == -1 else j + len(tag)
                buf.append(sql[i:j])
                i = j
            else:
                buf.append(c)
                i += 1
        elif c == ";":
            stmt = "".join(buf).strip()
            if _has_code(stmt):
                out.append(stmt)
            buf = []
            i += 1
        else:
            buf.append(c)
            i += 1
    tail = "".join(buf).strip()
    if _has_code(tail):
        out.append(tail)
    return out


def _has_code(stmt: str) -> bool:
    """True if the text has anything besides whitespace and comments."""
    stripped = re.sub(r"--[^\n]*|/\*.*?\*/", "", stmt, flags=re.S)
    return bool(stripped.strip())


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
                for stmt in split_statements(sql):
                    conn.execute(stmt)
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
