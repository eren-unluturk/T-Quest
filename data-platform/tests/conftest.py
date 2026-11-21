import pytest

from data_platform import db


@pytest.fixture
def db_conn():
    """Connection to DATABASE_URL; skips the test when the DB is unreachable."""
    try:
        conn = db.connect(connect_timeout=3)
    except Exception as exc:
        pytest.skip(f"database unreachable: {exc}")
    try:
        yield conn
    finally:
        conn.close()
