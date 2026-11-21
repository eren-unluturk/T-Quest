from data_platform.migrate import split_statements


def test_splits_simple_statements_and_drops_comment_only_tails():
    sql = "-- migrate:no-transaction\nSELECT 1;\nSELECT 2; -- trailing\n"
    assert split_statements(sql) == ["-- migrate:no-transaction\nSELECT 1", "SELECT 2"]


def test_semicolons_inside_quotes_and_dollar_bodies_do_not_split():
    sql = (
        "SELECT 'a;b';\n"
        "CREATE FUNCTION f() RETURNS int AS $$ BEGIN RETURN 1; END; $$ LANGUAGE plpgsql;\n"
        "DO $f$ BEGIN EXECUTE $g$ SELECT 1; $g$; END $f$;\n"
        "SELECT \"we;ird\";\n"
    )
    stmts = split_statements(sql)
    assert len(stmts) == 4
    assert stmts[0] == "SELECT 'a;b'"
    assert "RETURN 1; END;" in stmts[1]
