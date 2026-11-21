import json

import pytest

from data_platform import bench, migrate

SAMPLE_ENV = {
    "environment": "local",
    "params": {"synthetic_days": 1, "users": 10, "vehicles": 5, "poll_seconds": 15, "runs": 3},
    "row_counts": {"vehicles": 100, "predictions": 50, "rider_events": 40, "points_ledger": 30},
    "compression": {
        "vehicles": {"before_bytes": 4_000_000, "after_bytes": 400_000, "ratio": 10.0},
        "predictions": {"before_bytes": 0, "after_bytes": 0, "ratio": None},
    },
    "hypertable_bytes": {"rider_events": 1, "points_ledger": 1},
    "latency_ms": {
        "leaderboard_cagg": 1.0, "leaderboard_raw": 20.0, "home_line_cagg": 2.0,
        "home_line_raw": 30.0, "vehicles_at_stop_300s": 0.5,
    },
    "speedup_x": {"leaderboard": 20.0, "home_line": 15.0},
}


def test_median_ms_calls_warmup_plus_runs():
    calls = []
    value = bench.median_ms(lambda: calls.append(1), runs=5)
    assert len(calls) == 6
    assert value >= 0


def test_render_markdown_fills_every_number_and_handles_two_environments():
    tiger = dict(SAMPLE_ENV, environment="tiger_cloud")
    md = bench.render_markdown(
        {"generated_at": "2026-11-21T00:00:00+00:00", "environments": {"local": SAMPLE_ENV, "tiger_cloud": tiger}})
    assert "| Metric | local | tiger_cloud |" in md
    assert "10.0x" in md and "20.0x" in md
    assert "n/a" in md  # predictions have no compressed chunks yet
    assert "None" not in md


def test_smoke_tiny_run_writes_expected_json_keys_and_cleans_up(db_conn, tmp_path):
    migrate.migrate()
    args = ["--synthetic-days", "1", "--users", "10", "--vehicles", "5", "--runs", "2",
            "--out-dir", str(tmp_path)]
    try:
        assert bench.main(args) == 0
        results = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
        env = results["environments"]["local"]
        assert {"row_counts", "compression", "latency_ms", "speedup_x", "params"} <= set(env)
        assert {"leaderboard_cagg", "leaderboard_raw", "home_line_cagg", "home_line_raw",
                "vehicles_at_stop_300s"} <= set(env["latency_ms"])
        assert env["row_counts"]["vehicles"] > 0
        assert (tmp_path / "RESULTS.md").read_text(encoding="utf-8").startswith("# Benchmark results")
    finally:
        assert bench.main(["--cleanup"]) == 0
    db_conn.autocommit = True
    assert db_conn.execute("SELECT count(*) FROM users WHERE starts_with(username, 'bench_')").fetchone()[0] == 0
    assert db_conn.execute("SELECT count(*) FROM vehicles WHERE starts_with(vehicle_id, 'synthetic-')").fetchone()[0] == 0
    assert db_conn.execute("SELECT count(*) FROM points_ledger WHERE ref_type = 'synthetic'").fetchone()[0] == 0
