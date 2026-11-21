"""Connection helper. Reads DATABASE_URL (from env or a local .env file)."""
import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (copy .env.example to .env)")
    return url


def connect(url: str | None = None, **kwargs) -> psycopg.Connection:
    """Connect to `url`, or to DATABASE_URL when no url is given."""
    return psycopg.connect(url or database_url(), **kwargs)


def fetch_all(sql: str, params=None) -> list[dict]:
    """Run a read query on a short-lived connection and return rows as dicts."""
    with connect(row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchall()


def fetch_one(sql: str, params=None) -> dict | None:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None
