"""Rebuild contracts-draft/db/schema.sql by concatenating the migrations.

Usage: python -m data_platform.concat_schema

Use this only when no database is available. With a database, prefer a real dump:
    docker compose exec db pg_dump -U postgres -d tquest --schema-only --no-owner > contracts-draft/db/schema.sql
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEADER = """-- GENERATED FILE. Migrations in data-platform/migrations/ are the source of truth.
-- NOTE: this is a concatenation of migrations {first} to {last}, NOT a pg_dump. It was built
-- without a database. To replace it with a real dump, run from data-platform/:
--   docker compose up -d; python -m data_platform.migrate
--   docker compose exec db pg_dump -U postgres -d tquest --schema-only --no-owner > contracts-draft/db/schema.sql
-- (then re-add this header).

"""


def build() -> str:
    files = sorted((ROOT / "migrations").glob("[0-9][0-9][0-9][0-9]_*.sql"))
    out = HEADER.format(first=files[0].stem[:4], last=files[-1].stem[:4])
    for f in files:
        out += f"-- ===== migrations/{f.name} =====\n{f.read_text(encoding='utf-8').rstrip()}\n\n"
    return out


def main() -> None:
    target = ROOT / "contracts-draft" / "db" / "schema.sql"
    target.write_text(build(), encoding="utf-8", newline="\n")
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
