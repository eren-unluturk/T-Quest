import json

from data_platform import verify

URL = "postgres://tsdbadmin:s3cretpw@abc123.example.tsdb.cloud.timescale.com:5432/tsdb?sslmode=require"


def test_redact_removes_host_password_and_ips():
    text = ('connection to server at "abc123.example.tsdb.cloud.timescale.com" (10.1.2.3), port 5432 failed: '
            "password s3cretpw rejected; peer 192.168.0.9")
    out = verify.redact(text, [URL])
    for leaked in ("abc123.example", "s3cretpw", "10.1.2.3", "192.168.0.9"):
        assert leaked not in out


def test_environment_label():
    assert verify.environment_label(URL) == "tiger_cloud"
    assert verify.environment_label("postgresql://postgres:postgres@localhost:5432/tquest") == "local"
    assert verify.environment_label(None) == "unknown"


def test_failing_step_still_produces_full_report_and_nonzero_exit(tmp_path):
    def boom():
        raise RuntimeError('connection to server at "abc123.example.tsdb.cloud.timescale.com" failed')

    steps = [
        ("connect", lambda: {"summary": "PostgreSQL 16"}, None),
        ("migrate", boom, None),
        ("mbta", lambda: {}, "MBTA_API_KEY not set"),
        ("pytest", lambda: {"summary": "5 passed"}, None),
    ]
    code = verify.run(steps, tmp_path, "tiger_cloud", urls=[URL])
    assert code == 1

    report = json.loads((tmp_path / "verify.json").read_text(encoding="utf-8"))
    assert [s["status"] for s in report["steps"]] == ["pass", "fail", "skipped", "pass"]
    assert report["ok"] is False and report["failed_steps"] == ["migrate"]
    assert report["environment"] == "tiger_cloud"

    md = (tmp_path / "VERIFY.md").read_text(encoding="utf-8")
    assert "**FAIL**" in md and "(failed: migrate)" in md
    for name in ("connect", "migrate", "mbta", "pytest"):
        assert f"| {name} |" in md
    assert "abc123" not in md and "abc123" not in json.dumps(report)


def test_all_pass_exit_zero_and_skips_are_not_failures(tmp_path):
    steps = [("a", lambda: {"summary": "ok"}, None), ("b", lambda: {}, "skipped on purpose")]
    assert verify.run(steps, tmp_path, "local") == 0
    assert "**PASS**" in (tmp_path / "VERIFY.md").read_text(encoding="utf-8")


def test_introspection_tables_are_rendered(tmp_path):
    data = {"summary": "x", "hypertables": [{"hypertable_name": "vehicles", "num_chunks": 3, "compression_enabled": True}],
            "compression_settings": [], "jobs": [], "continuous_aggregates": []}
    verify.run([("timescaledb introspection", lambda: data, None)], tmp_path, "local")
    md = (tmp_path / "VERIFY.md").read_text(encoding="utf-8")
    assert "## Hypertables" in md and "| vehicles | 3 | True |" in md


def test_connect_failure_is_recorded_without_leaking_host_or_password(tmp_path, monkeypatch):
    import psycopg

    url = "postgresql://postgres:s3cretpw@localhost:1/tquest"

    def refuse(*args, **kwargs):
        raise psycopg.OperationalError(
            'connection failed: connection to server at "localhost" (::1), port 1 failed: '
            "Connection refused (password s3cretpw)")

    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setattr(verify.db, "connect", refuse)
    code = verify.run([("connect", verify.step_connect, None)], tmp_path, "local", urls=[url])
    assert code == 1
    report = json.loads((tmp_path / "verify.json").read_text(encoding="utf-8"))
    step = report["steps"][0]
    assert step["status"] == "fail" and "Connection refused" in step["error"]
    blob = json.dumps(report)
    assert "s3cretpw" not in blob and "localhost" not in blob
