from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded

from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.settings import get_settings
from app.routers import auth


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="Ad Spend Optimization API", version="0.1.0")

    # slowapi reads the limiter off app.state; the decorator on /api/auth/login needs both
    # this line and the handler below to turn RateLimitExceeded into a 429.
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.env}

    application.include_router(auth.router, prefix="/api/auth")

    return application


app = create_app()
