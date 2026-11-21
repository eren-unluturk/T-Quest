from data_platform import collector


def test_redact_removes_urls_and_keys(monkeypatch):
    monkeypatch.setenv("MBTA_API_KEY", "sekret123")
    out = collector.redact("failed postgresql://u:pw@host/db?sslmode=require key sekret123 api_key=abc")
    assert "pw@host" not in out and "sekret123" not in out and "abc" not in out
