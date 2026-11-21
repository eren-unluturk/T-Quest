"""DB-free checks on every migration and seed: the real Postgres parser (libpg_query via pglast)
must accept them, no-transaction files must split into individually parseable statements, and
the idempotency rules must hold. Semantic problems (types, FKs, TimescaleDB limits) still need a DB."""
import re
from pathlib import Path

import pytest
from pglast import parser

from data_platform.migrate import NO_TX_MARKER, split_statements

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = sorted((ROOT / "migrations").glob("*.sql"))
SEEDS = sorted((ROOT / "seeds").glob("*.sql"))
ALL_FILES = MIGRATIONS + SEEDS
NO_TX_FILES = [f for f in MIGRATIONS if f.read_text(encoding="utf-8").lstrip().startswith(NO_TX_MARKER)]


def _ids(files):
    return [f.name for f in files]


def _strip_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def test_files_were_found():
    assert len(MIGRATIONS) >= 7 and SEEDS


@pytest.mark.parametrize("path", ALL_FILES, ids=_ids(ALL_FILES))
def test_file_parses_with_postgres_parser(path):
    parser.parse_sql(path.read_text(encoding="utf-8"))


def test_no_transaction_files_are_detected():
    assert {f.name for f in NO_TX_FILES} >= {"0004_aggregates.sql", "0006_insights_aggregates.sql"}


@pytest.mark.parametrize("path", NO_TX_FILES, ids=_ids(NO_TX_FILES))
def test_no_transaction_split_matches_parser(path):
    text = path.read_text(encoding="utf-8")
    statements = split_statements(text)
    for stmt in statements:
        parser.parse_sql(stmt)  # each statement parses on its own
    assert len(statements) == len(parser.parse_sql(text))


@pytest.mark.parametrize("path", MIGRATIONS, ids=_ids(MIGRATIONS))
def test_timescale_calls_use_if_not_exists(path):
    sql = _strip_comments(path.read_text(encoding="utf-8"))
    pattern = r"\b(create_hypertable|add_compression_policy|add_retention_policy|add_continuous_aggregate_policy)\s*\((.*?)\)\s*;"
    for name, args in re.findall(pattern, sql, flags=re.S | re.I):
        assert re.search(r"if_not_exists\s*=>\s*TRUE", args, flags=re.I), f"{path.name}: {name}() lacks if_not_exists => TRUE"


@pytest.mark.parametrize("path", MIGRATIONS, ids=_ids(MIGRATIONS))
def test_create_statements_are_idempotent(path):
    sql = _strip_comments(path.read_text(encoding="utf-8"))
    for m in re.finditer(r"\bCREATE\s+(?!OR\s+REPLACE\b)((?:UNIQUE\s+)?(?:MATERIALIZED\s+VIEW|TABLE|INDEX|VIEW))\b(.{0,40})",
                         sql, flags=re.S | re.I):
        kind, rest = m.group(1), m.group(2)
        assert re.match(r"\s*IF\s+NOT\s+EXISTS\b", rest, flags=re.I), (
            f"{path.name}: CREATE {kind} {rest.strip()[:30]!r} needs IF NOT EXISTS or OR REPLACE")
