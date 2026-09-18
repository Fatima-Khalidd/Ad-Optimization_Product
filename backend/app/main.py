from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.errors import AppError
from app.core.middleware import (
    REQUEST_ID_HEADER,
    RequestContextMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
    configure_logging,
)
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.settings import Settings, get_settings
from app.routers import analysis, auth, reports, uploads


class CorsMisconfiguredError(RuntimeError):
    """Raised at startup rather than shipping an API any website can call with cookies."""


def _check_cors(settings: Settings) -> None:
    if settings.env != "prod":
        return
    if not settings.cors_origins or "*" in settings.cors_origins:
        raise CorsMisconfiguredError(
            "CORS_ORIGINS must list the exact frontend origin(s) in production; "
            f"got {settings.cors_origins!r}"
        )
    # F2: CORS_ORIGINS defaults to ["http://localhost:3000"] (dev convenience), so an
    # operator who forgets to set it in Railway would otherwise boot prod with the Vercel
    # frontend BLOCKED and localhost accepted as a credentialed origin. This also catches
    # any explicit localhost/127.0.0.1 entry, whether or not the rest of the list is real.
    localhost_origins = [
        origin for origin in settings.cors_origins if "localhost" in origin or "127.0.0.1" in origin
    ]
    if localhost_origins:
        raise CorsMisconfiguredError(
            "CORS_ORIGINS must not include a localhost/127.0.0.1 origin in production "
            f"(and must be explicitly set to the real frontend origin); got {localhost_origins!r}"
        )


def _init_sentry(settings: Settings) -> None:
    """Error reporting, off unless a DSN is configured.

    `send_default_pii=False` keeps client email addresses, cookies and request bodies out
    of Sentry — this app handles invoices and payment references (`docs/PLAN.md` §7).
    The FastAPI/Starlette integrations auto-enable; no integration list is needed.
    """
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env,
        send_default_pii=False,
        traces_sample_rate=0.0,
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    _init_sentry(settings)
    _check_cors(settings)
    application = FastAPI(title="Ad Spend Optimization API", version="0.1.0")

    # slowapi reads the limiter off app.state; the decorator on /api/auth/login needs both
    # this line and the handler below to turn RateLimitExceeded into a 429.
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Starlette runs middleware in reverse registration order: the LAST one added is the
    # OUTERMOST. Registration order here, outermost first:
    #   RequestContext -> SecurityHeaders -> CORS -> RequestSizeLimit -> routes
    # so every response, including a 413 and a rejected preflight, carries the security
    # headers and a request id.
    application.add_middleware(
        RequestSizeLimitMiddleware, max_bytes=settings.max_request_mb * 1024 * 1024
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
        max_age=600,
    )
    application.add_middleware(SecurityHeadersMiddleware, hsts=settings.env == "prod")
    application.add_middleware(RequestContextMiddleware)

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
    from app.routers.billing import router as billing_router

    application.include_router(admin_router)
    application.include_router(billing_router)

    return application


app = create_app()
