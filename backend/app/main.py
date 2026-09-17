from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.errors import AppError
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.settings import get_settings
from app.routers import analysis, auth, reports, uploads


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

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    application.include_router(auth.router, prefix="/api/auth")
    application.include_router(uploads.router)
    application.include_router(analysis.router)
    application.include_router(reports.router)

    from app.routers.admin import router as admin_router

    application.include_router(admin_router)

    return application


app = create_app()
