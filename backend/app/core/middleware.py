"""Cross-cutting HTTP concerns: security headers, request ids and structured logging.

Nothing here knows about the product. Each middleware does one thing, so `create_app()`
composes them in a deliberate order (see `app/main.py`).
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.rate_limit import client_ip_key

REQUEST_ID_HEADER = "X-Request-ID"
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), microphone=(), payment=(), usb=()"
)
HSTS_VALUE = "max-age=31536000; includeSubDomains"

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
access_logger = logging.getLogger("app.access")

_EXTRA_FIELDS = ("method", "path", "status", "duration_ms", "client_ip")


class JsonFormatter(logging.Formatter):
    """One JSON object per line, so Railway's log viewer can filter on the fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_var.get()),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging(level: str = "INFO") -> None:
    """Send every log line to stdout as JSON. Safe to call more than once."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn installs its own colourised handlers; drop them and let ours format instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True

    # F6(a): RequestContextMiddleware already emits one "app.access" line per request with
    # richer fields (request id, client ip). Leaving uvicorn.access propagating as well
    # doubles every access log line in production. It keeps its handlers cleared above (in
    # case anything ever logs to it directly) but stops bubbling up to root.
    logging.getLogger("uvicorn.access").propagate = False


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Headers every response gets. `hsts` is on only behind real TLS (prod)."""

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        super().__init__(app)
        self.hsts = hsts

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        if self.hsts:
            response.headers.setdefault("Strict-Transport-Security", HSTS_VALUE)
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Give every request an id, echo it back, and log one structured access line."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # F1: the same first-hop-of-X-Forwarded-For resolution the login rate limiter uses
        # (app.core.rate_limit.client_ip_key), so a lockout or an abuse pattern is
        # diagnosable from the access log in production instead of showing Railway's
        # single proxy address for every request.
        client_ip = client_ip_key(request)
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming if incoming and SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            access_logger.exception(
                "request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "request_id": request_id,
                    "client_ip": client_ip,
                },
            )
            raise
        finally:
            request_id_var.reset(token)

        response.headers[REQUEST_ID_HEADER] = request_id
        access_logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "request_id": request_id,
                "client_ip": client_ip,
            },
        )
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized requests on their headers, before any body is read.

    This is the blunt outer guard. The upload endpoint keeps its own, smaller
    `max_upload_mb` cap on the file itself (Stage 3).

    F6(c): this only checks `Content-Length`, so a chunked-transfer-encoding body (no
    `Content-Length` header at all) sails past this middleware regardless of size - no code
    change here is the right call, because the real gate for that case already exists at
    the endpoint level: `app/routers/uploads.py::_read_limited` reads the upload a chunk at
    a time and aborts as soon as the running total exceeds `max_upload_mb`, so a chunked
    body still cannot grow an `UploadFile` past the configured cap. Any endpoint that reads
    a request body without going through that pattern would NOT be protected against a
    chunked body by this middleware alone.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw_length = request.headers.get("content-length")
        if raw_length is not None:
            try:
                length = int(raw_length)
            except ValueError:
                return JSONResponse({"detail": "invalid Content-Length"}, status_code=400)
            if length > self.max_bytes:
                return JSONResponse({"detail": "request body too large"}, status_code=413)
        return await call_next(request)
