import re
from pathlib import Path

import pytest

SQL = Path(__file__).resolve().parent.parent / "sql"
FILES = [
    "analytics_me.sql",
    "recs_unvisited_neighborhoods.sql",
    "recs_routes.sql",
    "recs_place_affinity.sql",
]
AGGREGATES = ("time_bucket", "user_stop_daily", "stop_popularity_hourly", "home_line")
ALLOWED_PARAMS = {"user_id", "since", "limit"}


@pytest.mark.parametrize("name", FILES)
def test_sql_file(name):
    text = (SQL / name).read_text(encoding="utf-8")
    assert text.lstrip().startswith("--"), "needs a header comment"
    assert "Reads" in text.split("\n\n")[0] + text[:1500]
    assert any(a in text for a in AGGREGATES)
    params = set(re.findall(r"%\((\w+)\)s", text))
    assert "user_id" in params
    assert params <= ALLOWED_PARAMS, params


def test_place_affinity_states_consent_gate():
    text = (SQL / "recs_place_affinity.sql").read_text(encoding="utf-8")
    assert "has_consent" in text and "place_visits" in text
    assert "CONSENT GATE" in text


def test_only_place_affinity_reads_place_visits_table():
    for name in FILES:
        body = "\n".join(
            line
            for line in (SQL / name).read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("--")
        )
        reads = re.search(r"\b(FROM|JOIN)\s+place_visits\b", body) is not None
        assert reads == (name == "recs_place_affinity.sql"), name


def test_weekly_series_uses_time_bucket():
    assert "time_bucket('1 week'" in (SQL / "analytics_me.sql").read_text(encoding="utf-8")
