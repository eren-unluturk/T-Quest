from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .routes import realtime, routes, stops

app = FastAPI(title="T-Quest data-platform", version="0.1.0")

# Public read API: no user data, so any origin may call it.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

app.include_router(routes.router)
app.include_router(stops.router)
app.include_router(realtime.router)


@app.get("/health")
def health() -> dict:
    try:
        with db.connect(connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        ok = True
    except Exception:
        ok = False
    return {"status": "ok", "db": ok}
