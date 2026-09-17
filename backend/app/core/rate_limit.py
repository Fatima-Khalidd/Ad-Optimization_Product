"""The slowapi limiter singleton. Login is the only rate-limited route (docs/PLAN.md section 5).

The Limiter lives at module level (not inside create_app) so tests can disable it, and so
every app instance in one process shares the same counters.
"""

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

LOGIN_RATE_LIMIT = "5/minute"

limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "too many requests"})
