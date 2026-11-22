import pytest

from data_platform.seed_demo import check_urls

A = "postgres://u:p@host-a.example.invalid:5432/db1"


def test_refuses_same_url():
    with pytest.raises(SystemExit, match="same database"):
        check_urls(A, A)


def test_refuses_same_host_and_db_even_if_credentials_differ():
    with pytest.raises(SystemExit, match="same database"):
        check_urls("postgres://other:x@host-a.example.invalid:5432/db1?sslmode=require", A)


def test_refuses_missing_urls():
    with pytest.raises(SystemExit):
        check_urls(None, A)
    with pytest.raises(SystemExit):
        check_urls(A, None)


def test_allows_different_database():
    check_urls("postgres://u:p@host-b.example.invalid:5432/db2", A)


def test_error_messages_never_contain_the_url():
    try:
        check_urls(A, A)
    except SystemExit as e:
        assert "host-a" not in str(e) and "u:p" not in str(e)
