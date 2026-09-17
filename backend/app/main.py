from fastapi import FastAPI

from app.core.settings import get_settings
from app.routers import auth


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="Ad Spend Optimization API", version="0.1.0")

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.env}

    application.include_router(auth.router, prefix="/api/auth")

    # NOTE: app.state.limiter / SlowAPIMiddleware / the RateLimitExceeded exception handler
    # are deliberately NOT wired here. `/api/auth/login` already carries
    # `@limiter.limit(LOGIN_RATE_LIMIT)` (Task 6), and slowapi no-ops that decorator while
    # `limiter.enabled` is False (the default in tests/api/conftest.py), so it works today
    # without touching this app. Registering the middleware/handler pair is Task 7's job.

    return application


app = create_app()
