from data_platform import migrate


def test_migrate_twice_is_idempotent(db_conn):
    migrate.migrate()
    count1 = db_conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    db_conn.commit()

    second = migrate.migrate()
    count2 = db_conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    db_conn.commit()

    assert second == []
    assert count1 == count2 >= 1
    ext = db_conn.execute("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'").fetchone()
    assert ext is not None
