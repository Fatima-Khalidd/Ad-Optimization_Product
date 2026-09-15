from fastapi import FastAPI

from app.core.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="Ad Spend Optimization API", version="0.1.0")

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.env}

    return application


app = create_app()
