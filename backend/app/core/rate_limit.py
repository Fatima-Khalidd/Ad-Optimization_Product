"""The slowapi limiter singleton. Login is the only rate-limited route (docs/PLAN.md section 5).

The Limiter lives at module level (not inside create_app) so tests can disable it, and so
every app instance in one process shares the same counters.
"""

import ipaddress

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

LOGIN_RATE_LIMIT = "5/minute"


def client_ip_key(request: Request) -> str:
    """Rate-limit (and access-log) key: the caller's IP as seen through our own proxy.

    On Railway every request reaches uvicorn through Railway's edge proxy, so
    `request.client.host` (what `get_remote_address` reads) is the PROXY's address, not
    the caller's - every client would share one bucket, and five failed logins from one
    attacker would lock out everybody (F1). `backend/Procfile` runs uvicorn with
    `--forwarded-allow-ips` set so uvicorn trusts the proxy and exposes the chain via
    `X-Forwarded-For`; we key on the FIRST hop of that header, which is the address the
    proxy itself recorded for the original caller.

    Trusting only the first hop is what makes this safe with exactly ONE trusted proxy in
    front of the app: a client cannot forge extra `X-Forwarded-For` entries to make itself
    look like someone else, because the first entry a single well-behaved proxy writes is
    the connection it actually received.

    WARNING - this header is fully attacker-controlled if the app is ever reachable
    WITHOUT a trusted proxy in front of it (e.g. hit directly, bypassing Railway): in that
    case a caller can set any `X-Forwarded-For` it likes and evade the limiter entirely.
    The alternative - trusting `request.client.host` unconditionally - is worse in our
    actual deployment: a global lockout, not a spoofable one.
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
limiter = Limiter(key_func=client_ip_key, strategy="moving-window")


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "too many requests"})
