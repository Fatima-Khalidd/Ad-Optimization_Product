"""The slowapi limiter singleton. Login is the only rate-limited route (docs/PLAN.md section 5)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

LOGIN_RATE_LIMIT = "5/minute"

limiter = Limiter(key_func=get_remote_address)
