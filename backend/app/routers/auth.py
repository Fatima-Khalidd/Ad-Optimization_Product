"""/api/auth - the only routes that mint or clear auth cookies."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.deps import CurrentUser
from app.core.rate_limit import LOGIN_RATE_LIMIT, limiter
from app.core.security import (
    REFRESH_COOKIE,
    InvalidTokenError,
    clear_auth_cookies,
    decode_token,
    set_auth_cookies,
)
from app.models import User
from app.schemas.auth import ClientOut, LoginRequest, MeOut, SignupRequest, UserOut
from app.services.auth import EmailTakenError, authenticate, client_for, signup_client

router = APIRouter(tags=["auth"])


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")


def _me(session: Session, user: User) -> MeOut:
    client = client_for(session, user) if user.role == "client" else None
    return MeOut(
        user=UserOut.model_validate(user),
        client=ClientOut.model_validate(client) if client is not None else None,
    )


@router.post("/signup", response_model=MeOut, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest, response: Response, session: Session = Depends(get_session)
) -> MeOut:
    try:
        user = signup_client(session, payload.email, payload.password, payload.business_name)
    except EmailTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email already registered"
        ) from None
    set_auth_cookies(response, user_id=user.id, role=user.role)
    return _me(session, user)


@router.post("/login", response_model=MeOut)
@limiter.limit(LOGIN_RATE_LIMIT)
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> MeOut:
    # `request` is unused here but slowapi requires a parameter named exactly "request".
    user = authenticate(session, payload.email, payload.password)
    if user is None:
        raise _unauthorized()
    set_auth_cookies(response, user_id=user.id, role=user.role)
    return _me(session, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response)
    return response


@router.post("/refresh", response_model=MeOut)
def refresh(request: Request, response: Response, session: Session = Depends(get_session)) -> MeOut:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise _unauthorized()
    try:
        payload = decode_token(token)
    except InvalidTokenError:
        raise _unauthorized() from None
    if payload.typ != "refresh":
        raise _unauthorized()
    user = session.get(User, payload.sub)
    if user is None or not user.is_active:
        raise _unauthorized()
    # Rotate both cookies on every refresh.
    set_auth_cookies(response, user_id=user.id, role=user.role)
    return _me(session, user)


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser, session: Session = Depends(get_session)) -> MeOut:
    return _me(session, user)
