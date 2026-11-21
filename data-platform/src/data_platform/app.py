from fastapi import FastAPI

from . import db

app = FastAPI(title="T-Quest data-platform")


@app.get("/health")
def health() -> dict:
    try:
        with db.connect(connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        ok = True
    except Exception:
        ok = False
    return {"status": "ok", "db": ok}
