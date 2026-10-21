"""The slowapi limiter singleton. Login is the only rate-limited route (docs/PLAN.md section 5).

The Limiter lives at module level (not inside create_app) so tests can disable it, and so
every app instance in one process shares the same counters. Counters live wherever
RATE_LIMIT_STORAGE_URI points: process memory by default, a shared Redis on serverless,
where each concurrent function instance would otherwise count on its own.
"""

import ipaddress

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.settings import get_settings

LOGIN_RATE_LIMIT = "5/minute"


def client_ip_key(request: Request) -> str:
    """Rate-limit (and access-log) key: the caller's IP as seen through our own proxy.

    On Vercel every request reaches the function through Vercel's edge, so the socket peer
    (what `get_remote_address` reads) is never the caller. Vercel's edge writes the
    caller's address into `X-Forwarded-For` itself rather than passing through a value the
    client sent, so the FIRST hop of that header is the address the edge actually
    received the connection from. Keying on anything shared by every request would put all
    clients in one bucket, and five failed logins from one attacker would lock out
    everybody, including the admin (F1).

    WARNING - this header is fully attacker-controlled if the app is ever reachable
    WITHOUT a trusted proxy in front of it (e.g. a uvicorn port exposed directly): in that
    case a caller can set any `X-Forwarded-For` it likes and evade the limiter entirely.
    The alternative - trusting the socket peer unconditionally - is worse in our actual
    deployment: a global lockout, not a spoofable one.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            pass
        else:
            return candidate
    return get_remote_address(request)


# moving-window (not the slowapi default of fixed-window) so a login burst spanning a
# minute boundary can't reset the counter mid-test and let a 6th attempt through.
limiter = Limiter(
    key_func=client_ip_key,
    strategy="moving-window",
    storage_uri=get_settings().rate_limit_storage_uri,
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "too many requests"})
