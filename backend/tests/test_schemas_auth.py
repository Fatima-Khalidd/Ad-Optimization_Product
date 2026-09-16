import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, MeOut, SignupRequest


def test_signup_accepts_a_valid_body():
    payload = SignupRequest(
        email="Owner@Example.COM", password="longenough", business_name="Karachi Kicks"
    )

    assert payload.password == "longenough"
    assert payload.business_name == "Karachi Kicks"


def test_signup_rejects_a_short_password():
    with pytest.raises(ValidationError) as excinfo:
        SignupRequest(email="a@example.com", password="short12", business_name="X")

    assert "password" in str(excinfo.value)


def test_signup_rejects_a_bad_email():
    with pytest.raises(ValidationError):
        SignupRequest(email="not-an-email", password="longenough", business_name="X")


def test_signup_rejects_an_empty_business_name():
    with pytest.raises(ValidationError):
        SignupRequest(email="a@example.com", password="longenough", business_name="")


def test_signup_rejects_a_business_name_over_200_chars():
    with pytest.raises(ValidationError):
        SignupRequest(email="a@example.com", password="longenough", business_name="x" * 201)


def test_signup_has_no_role_field_and_silently_drops_one():
    # The only defence that matters: even if a caller sends "role", it cannot reach the service.
    payload = SignupRequest(
        email="a@example.com",
        password="longenough",
        business_name="X",
        role="admin",
    )

    assert "role" not in SignupRequest.model_fields
    assert not hasattr(payload, "role")
    assert payload.model_dump() == {
        "email": "a@example.com",
        "password": "longenough",
        "business_name": "X",
    }


def test_login_requires_both_fields():
    with pytest.raises(ValidationError):
        LoginRequest(email="a@example.com")


def test_login_has_no_role_field_and_silently_drops_one():
    payload = LoginRequest(email="a@example.com", password="longenough", role="admin")

    assert "role" not in LoginRequest.model_fields
    assert not hasattr(payload, "role")


def test_me_out_builds_from_orm_user_and_client_rows(session):
    from app.schemas.auth import ClientOut, UserOut
    from tests.api.helpers import make_client, user_for

    client_row = make_client(session, email="owner@example.com", business_name="Karachi Kicks")
    user_row = user_for(session, client_row)

    me = MeOut(
        user=UserOut.model_validate(user_row),
        client=ClientOut.model_validate(client_row),
    )

    assert me.user.email == "owner@example.com"
    assert me.user.role == "client"
    assert me.client is not None
    assert me.client.business_name == "Karachi Kicks"
    assert str(me.client.base_fee) == "15000.00"


def test_me_out_client_is_none_for_an_admin_user(session):
    from app.schemas.auth import UserOut
    from tests.api.helpers import make_admin

    admin = make_admin(session, email="admin@example.com")

    me = MeOut(user=UserOut.model_validate(admin), client=None)

    assert me.user.role == "admin"
    assert me.client is None
