from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Response

from app.core.security import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    InvalidTokenError,
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    set_auth_cookies,
    verify_password,
)

# Anchored to real wall-clock time at import, rather than a hardcoded calendar date:
# jwt.decode() validates both "exp" and "iat" against the real clock (iat must not be in the
# future, exp must not be in the past), so a literal fixture would flake once enough real time
# has elapsed since this file was written. Module-import time is always <= decode time and
# well within the access/refresh token lifetimes, so both checks pass.
FIXED_NOW = datetime.now(UTC).replace(microsecond=0)


def test_hash_round_trip():
    hashed = hash_password("correct-horse-battery")

    assert hashed.startswith("$argon2id$")
    assert hashed != "correct-horse-battery"
    assert verify_password("correct-horse-battery", hashed) is True


def test_wrong_password_is_false():
    hashed = hash_password("correct-horse-battery")

    assert verify_password("correct-horse-batteryX", hashed) is False
    assert verify_password("", hashed) is False


def test_each_hash_gets_its_own_salt():
    assert hash_password("same") != hash_password("same")


def test_verify_against_garbage_is_false_not_an_exception():
    assert verify_password("anything", "not-a-hash") is False


def test_access_token_decodes_with_role_and_type():
    token = create_access_token(42, "client", now=FIXED_NOW)

    payload = decode_token(token)

    assert payload.sub == 42
    assert payload.role == "client"
    assert payload.typ == "access"
    # ACCESS_TOKEN_MINUTES is 15 -> exactly 900 seconds of life.
    assert payload.exp - payload.iat == 900
    assert payload.exp == int((FIXED_NOW + timedelta(minutes=15)).timestamp())


def test_refresh_token_has_typ_refresh_and_no_role():
    token = create_refresh_token(42, now=FIXED_NOW)

    payload = decode_token(token)

    assert payload.sub == 42
    assert payload.typ == "refresh"
    assert payload.role is None
    # REFRESH_TOKEN_DAYS is 7 -> 7 * 86400 seconds.
    assert payload.exp - payload.iat == 604800


def test_two_tokens_for_the_same_user_are_never_identical():
    # Rotation on /api/auth/refresh must visibly change the cookie even within one second.
    assert create_access_token(1, "client", now=FIXED_NOW) != create_access_token(
        1, "client", now=FIXED_NOW
    )


def test_expired_token_raises():
    stale = datetime.now(UTC) - timedelta(minutes=30)  # exp lands 15 minutes in the past
    token = create_access_token(42, "client", now=stale)

    with pytest.raises(InvalidTokenError):
        decode_token(token)


def test_tampered_token_raises():
    token = create_access_token(42, "client")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    with pytest.raises(InvalidTokenError):
        decode_token(tampered)


def test_token_signed_with_another_secret_raises():
    import jwt

    forged = jwt.encode(
        {"sub": "42", "role": "admin", "typ": "access", "exp": 4102444800, "iat": 0},
        "not-our-secret",
        algorithm="HS256",
    )

    with pytest.raises(InvalidTokenError):
        decode_token(forged)


def test_token_without_a_type_claim_raises():
    import jwt

    from app.core.settings import get_settings

    naked = jwt.encode(
        {"sub": "42", "exp": 4102444800, "iat": 0},
        get_settings().secret_key,
        algorithm="HS256",
    )

    with pytest.raises(InvalidTokenError):
        decode_token(naked)


def test_cookie_names_match_the_interface_contract():
    assert ACCESS_COOKIE == "access_token"
    assert REFRESH_COOKIE == "refresh_token"


def test_set_auth_cookies_sets_both_cookies_httponly_lax_and_path():
    response = Response()

    set_auth_cookies(response, user_id=42, role="client")

    cookies = response.headers.getlist("set-cookie")
    assert len(cookies) == 2
    access_cookie = next(c for c in cookies if c.startswith(f"{ACCESS_COOKIE}="))
    refresh_cookie = next(c for c in cookies if c.startswith(f"{REFRESH_COOKIE}="))
    for cookie in (access_cookie, refresh_cookie):
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie
        assert "Path=/" in cookie


def test_set_auth_cookies_secure_flag_mirrors_settings(monkeypatch):
    from app.core.settings import get_settings

    monkeypatch.setenv("COOKIE_SECURE", "true")
    get_settings.cache_clear()
    try:
        response = Response()
        set_auth_cookies(response, user_id=42, role="client")
        for cookie in response.headers.getlist("set-cookie"):
            assert "Secure" in cookie
    finally:
        get_settings.cache_clear()


def test_set_auth_cookies_not_secure_when_settings_say_so():
    response = Response()

    set_auth_cookies(response, user_id=42, role="client")

    for cookie in response.headers.getlist("set-cookie"):
        assert "Secure" not in cookie


def test_set_auth_cookies_values_decode_to_matching_payloads():
    response = Response()

    set_auth_cookies(response, user_id=7, role="admin")

    cookies = response.headers.getlist("set-cookie")
    access_raw = next(c for c in cookies if c.startswith(f"{ACCESS_COOKIE}="))
    refresh_raw = next(c for c in cookies if c.startswith(f"{REFRESH_COOKIE}="))
    access_token = access_raw.split(";", 1)[0].split("=", 1)[1]
    refresh_token = refresh_raw.split(";", 1)[0].split("=", 1)[1]

    access_payload = decode_token(access_token)
    refresh_payload = decode_token(refresh_token)

    assert access_payload.sub == 7
    assert access_payload.role == "admin"
    assert access_payload.typ == "access"
    assert refresh_payload.sub == 7
    assert refresh_payload.typ == "refresh"


def test_clear_auth_cookies_expires_both():
    response = Response()

    clear_auth_cookies(response)

    cookies = response.headers.getlist("set-cookie")
    assert len(cookies) == 2
    for cookie in cookies:
        assert "Max-Age=0" in cookie or cookie.split(";")[0].endswith("=")
