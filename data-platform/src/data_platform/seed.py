"""Apply seeds/dev_seed.sql. Usage: python -m data_platform.seed"""
import sys
from pathlib import Path

from . import db

SEED_FILE = Path(__file__).resolve().parents[2] / "seeds" / "dev_seed.sql"


def seed(path: Path = SEED_FILE) -> None:
    with db.connect() as conn:
        conn.execute(path.read_text(encoding="utf-8"))
    print(f"seeded from {path.name}")


if __name__ == "__main__":
    seed()
    sys.exit(0)
