"""Password hashing and JWT minting/validation.

Knows nothing about routes or the database: everything here takes plain values so it can be
unit-tested without a client or a session.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from fastapi import Response
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.settings import get_settings

__all__ = [
    "ACCESS_COOKIE",
    "ALGORITHM",
    "REFRESH_COOKIE",
    "InvalidTokenError",
    "TokenPayload",
    "clear_auth_cookies",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "set_auth_cookies",
    "verify_password",
]

ALGORITHM = "HS256"
ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

# Argon2id with the library's recommended parameters (docs/PLAN.md section 5).
_hasher = PasswordHash.recommended()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(plain, hashed)
    except Exception:  # a malformed or empty stored hash is a failed login, not a 500
        return False


@dataclass(frozen=True)
class TokenPayload:
    sub: int
    role: str | None
    typ: str
    exp: int
    iat: int


def _encode(claims: dict[str, Any], lifetime: timedelta, now: datetime | None) -> str:
    settings = get_settings()
    issued = now or datetime.now(UTC)
    payload = {
        **claims,
        "iat": int(issued.timestamp()),
        "exp": int((issued + lifetime).timestamp()),
        # Makes every token unique even when two are minted in the same second, so cookie
        # rotation on /api/auth/refresh is always observable.
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: int, role: str, *, now: datetime | None = None) -> str:
    minutes = get_settings().access_token_minutes
    return _encode(
        {"sub": str(user_id), "role": role, "typ": "access"}, timedelta(minutes=minutes), now
    )


def create_refresh_token(user_id: int, *, now: datetime | None = None) -> str:
    days = get_settings().refresh_token_days
    return _encode({"sub": str(user_id), "typ": "refresh"}, timedelta(days=days), now)


def decode_token(token: str) -> TokenPayload:
    """Verify signature and expiry. Raises jwt.exceptions.InvalidTokenError on anything wrong."""
    claims = jwt.decode(
        token,
        get_settings().secret_key,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "iat", "sub", "typ"]},
    )
    try:
        subject = int(claims["sub"])
    except (TypeError, ValueError):
        raise InvalidTokenError("token subject is not a user id") from None
    typ = claims["typ"]
    if typ not in ("access", "refresh"):
        raise InvalidTokenError(f"unknown token type: {typ}")
    return TokenPayload(
        sub=subject,
        role=claims.get("role"),
        typ=typ,
        exp=int(claims["exp"]),
        iat=int(claims["iat"]),
    )


def _cookie_kwargs() -> dict[str, Any]:
    return {
        "httponly": True,
        "secure": get_settings().cookie_secure,
        "samesite": "lax",
        "path": "/",
    }


def set_auth_cookies(response: Response, *, user_id: int, role: str) -> None:
    settings = get_settings()
    response.set_cookie(
        ACCESS_COOKIE,
        create_access_token(user_id, role),
        max_age=settings.access_token_minutes * 60,
        **_cookie_kwargs(),
    )
    response.set_cookie(
        REFRESH_COOKIE,
        create_refresh_token(user_id),
        max_age=settings.refresh_token_days * 86400,
        **_cookie_kwargs(),
    )


def clear_auth_cookies(response: Response) -> None:
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(name, **_cookie_kwargs())
