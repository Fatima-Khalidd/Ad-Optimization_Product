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

# moving-window (not the slowapi default of fixed-window) so a login burst spanning a
# minute boundary can't reset the counter mid-test and let a 6th attempt through.
limiter = Limiter(key_func=get_remote_address, strategy="moving-window")


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "too many requests"})
