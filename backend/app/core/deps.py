"""Turning the access_token cookie into a User or a Client.

This is the only place in the codebase that reads an auth cookie, and the only place a
role is checked. Client-facing endpoints take their client_id from CurrentClient and never
from the request body or path (docs/PLAN.md section 4 "Tenant isolation").
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.security import ACCESS_COOKIE, InvalidTokenError, decode_token
from app.models import Client, User


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise _unauthorized()
    try:
        payload = decode_token(token)
    except InvalidTokenError:
        raise _unauthorized() from None
    if payload.typ != "access":
        raise _unauthorized()
    user = session.get(User, payload.sub)
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    # The stored role decides, never the "role" claim in the token.
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return user


def require_client(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> Client:
    if user.role != "client":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="client only")
    client = session.scalar(select(Client).where(Client.user_id == user.id))
    if client is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="client only")
    return client


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentClient = Annotated[Client, Depends(require_client)]
CurrentAdmin = Annotated[User, Depends(require_admin)]
