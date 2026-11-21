"""Benchmark helpers. Full benchmark lands in a later prompt."""
from . import db

HYPERTABLES = ("vehicles", "predictions")


def compression_stats(tables: tuple[str, ...] = HYPERTABLES) -> dict[str, dict]:
    """Before/after bytes and ratio per hypertable (ratio is None until a chunk is compressed)."""
    out: dict[str, dict] = {}
    with db.connect() as conn:
        for table in tables:
            row = conn.execute(
                "SELECT coalesce(sum(before_compression_total_bytes), 0),"
                "       coalesce(sum(after_compression_total_bytes), 0)"
                " FROM hypertable_compression_stats(%s::regclass)",
                (table,),
            ).fetchone()
            before, after = int(row[0]), int(row[1])
            out[table] = {
                "before_bytes": before,
                "after_bytes": after,
                "ratio": (before / after) if after else None,
            }
    return out
