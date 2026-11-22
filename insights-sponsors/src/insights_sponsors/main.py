from fastapi import FastAPI
from . import _shared  # noqa: F401
import tquest_auth
import tquest_http

from .config import settings
from .routes import catalog, consent, content, insights, place_visits, spots, faves, login


def create_app() -> FastAPI:
    prod = tquest_auth.app_env() == "prod"
    app = FastAPI(
        title="T-Quest insights-sponsors", version="0.1.0",
        docs_url=None if prod else "/docs", redoc_url=None, openapi_url=None if prod else "/openapi.json",
    )
    tquest_http.harden(app)  # CORS from CORS_ORIGINS, rate limits, body limit, security headers, generic errors
    app.include_router(content.router)
    app.include_router(catalog.router)
    app.include_router(consent.router)
    app.include_router(insights.router)
    app.include_router(place_visits.router)
    app.include_router(spots.router)
    app.include_router(faves.router)
    app.include_router(login.router)

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "service": "insights-sponsors",
            "data_backend": settings.data_backend,
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)
