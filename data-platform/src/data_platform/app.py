from fastapi import FastAPI
from . import _shared  # noqa: F401
import tquest_auth
import tquest_http

from . import db
from .routes import realtime, routes, stops, travel

_prod = tquest_auth.app_env() == "prod"
app = FastAPI(
    title="T-Quest data-platform", version="0.1.0",
    docs_url=None if _prod else "/docs", redoc_url=None, openapi_url=None if _prod else "/openapi.json",
)
# Read API: CORS from CORS_ORIGINS (exact origins in prod), security headers, generic errors.
tquest_http.harden(app, allow_methods=("GET", "OPTIONS"))

app.include_router(routes.router)
app.include_router(stops.router)
app.include_router(realtime.router)
app.include_router(travel.router)


@app.get("/health")
def health() -> dict:
    ok = False
    last_vehicle_at = None
    try:
        with db.connect(connect_timeout=3) as conn:
            conn.execute("SELECT 1")
            ok = True
            # Freshness of the live feed: newest vehicle row (recent chunks only, so this stays cheap).
            row = conn.execute("SELECT max(time) FROM vehicles WHERE time > now() - interval '1 day'").fetchone()
            last_vehicle_at = row[0].isoformat() if row and row[0] else None
    except Exception:
        pass
    return {"status": "ok", "db": ok, "last_vehicle_at": last_vehicle_at}
