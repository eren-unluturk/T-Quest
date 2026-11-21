"""Connection helper. Reads DATABASE_URL (from env or a local .env file)."""
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (copy .env.example to .env)")
    return url


def connect(**kwargs) -> psycopg.Connection:
    return psycopg.connect(database_url(), **kwargs)
