from fastapi import FastAPI

from .config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="T-Quest insights-sponsors", version="0.1.0")

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
