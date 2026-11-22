import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tquest_auth as A  # noqa: E402

SECRET = "x" * 32


def test_valid_token_roundtrip():
    t = A.issue_token("demoRider1", SECRET)
    assert A.verify_token(t, SECRET) == "demoRider1"


def test_expired_token():
    t = A.issue_token("demoRider1", SECRET, ttl_s=60, now=1000)
    with pytest.raises(A.AuthError, match="expired"):
        A.verify_token(t, SECRET, now=1061)
    assert A.verify_token(t, SECRET, now=1059) == "demoRider1"


def test_tampered_token():
    t = A.issue_token("demoRider1", SECRET)
    payload, sig = t.split(".")
    other = A.issue_token("someoneElse", SECRET)
    with pytest.raises(A.AuthError):
        A.verify_token(other.split(".")[0] + "." + sig, SECRET)  # swapped payload
    with pytest.raises(A.AuthError):
        A.verify_token(payload + "." + sig[:-2] + "AA", SECRET)  # altered signature
    with pytest.raises(A.AuthError):
        A.verify_token("garbage", SECRET)


def test_wrong_secret():
    t = A.issue_token("demoRider1", SECRET)
    with pytest.raises(A.AuthError):
        A.verify_token(t, "y" * 32)


def test_missing_header_and_prod_rules(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("TOKEN_SECRET", SECRET)
    for h in (None, "", "Bearer", "Bearer ", "Basic abc"):
        with pytest.raises(A.AuthError):
            A.user_from_authorization(h)
    with pytest.raises(A.AuthError):  # a plain username is NOT accepted in prod
        A.user_from_authorization("Bearer demoRider1")
    t = A.issue_token("demoRider1", SECRET)
    assert A.user_from_authorization(f"Bearer {t}") == "demoRider1"


def test_dev_accepts_plain_username(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    assert A.user_from_authorization("Bearer ann") == "ann"


def test_username_rules():
    assert A.valid_username("abc") and A.valid_username("a" * 32)
    for bad in ("ab", "a" * 33, "has space", "a@b.com", "", "user_name"):
        assert not A.valid_username(bad)
    with pytest.raises(ValueError):
        A.issue_token("a@b.com", SECRET)


def test_prod_fails_closed_without_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("TOKEN_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        A.require_prod_config()
    monkeypatch.setenv("TOKEN_SECRET", "short")
    with pytest.raises(RuntimeError):
        A.require_prod_config()
