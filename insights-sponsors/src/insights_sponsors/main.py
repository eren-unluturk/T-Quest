from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import catalog, consent, content, insights, place_visits, spots, faves


def create_app() -> FastAPI:
    app = FastAPI(title="T-Quest insights-sponsors", version="0.1.0")
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"]
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"], allow_credentials=False,
    )
    app.include_router(content.router)
    app.include_router(catalog.router)
    app.include_router(consent.router)
    app.include_router(insights.router)
    app.include_router(place_visits.router)
    app.include_router(spots.router)
    app.include_router(faves.router)

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
