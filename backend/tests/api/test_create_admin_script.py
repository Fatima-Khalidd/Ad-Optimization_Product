"""Drives scripts.create_admin.main() directly against the shared bound engine, so no
subprocess is needed - `db` (tests/api/conftest.py) and this call see the same rows.

Deliberately NOT a subprocess test: the bound-engine fixtures only work in-process, and a
subprocess would need its own DATABASE_URL wiring that duplicates tests/conftest.py.
"""

import pytest
from sqlalchemy import select

from app.models import Client, User
from scripts.create_admin import main


def test_creates_an_admin_and_no_client_row(db, capsys):
    exit_code = main(["--email", "Boss@Example.com", "--password", "longenough"])

    assert exit_code == 0

    out = capsys.readouterr().out
    assert "boss@example.com" in out
    assert "longenough" not in out

    user = db.scalar(select(User).where(User.email == "boss@example.com"))
    assert user is not None
    assert user.role == "admin"
    assert user.is_active is True
    assert user.password_hash.startswith("$argon2id$")
    assert f"id={user.id}" in out

    assert db.scalar(select(Client).where(Client.user_id == user.id)) is None


def test_refuses_a_duplicate_email(db, capsys):
    assert main(["--email", "boss@example.com", "--password", "longenough"]) == 0

    exit_code = main(["--email", "BOSS@example.com", "--password", "otherpassword"])

    assert exit_code == 2
    err = capsys.readouterr().err
    assert "already registered" in err

    assert len(list(db.scalars(select(User)))) == 1


def test_refuses_a_short_password(db, capsys):
    exit_code = main(["--email", "new@example.com", "--password", "short12"])

    assert exit_code == 2
    assert "at least 8 characters" in capsys.readouterr().err
    assert db.scalar(select(User).where(User.email == "new@example.com")) is None


def test_refuses_an_empty_password(db, capsys):
    exit_code = main(["--email", "new@example.com", "--password", ""])

    assert exit_code == 2
    assert "at least 8 characters" in capsys.readouterr().err


def test_refuses_an_invalid_email(db, capsys):
    exit_code = main(["--email", "not-an-email", "--password", "longenough"])

    assert exit_code == 2
    err = capsys.readouterr().err
    assert "email" in err.lower()
    assert db.scalar(select(User)) is None


def test_prompts_for_the_password_when_omitted(db, capsys, monkeypatch):
    monkeypatch.setattr("scripts.create_admin.getpass", lambda prompt="": "prompted-pw")

    exit_code = main(["--email", "prompted@example.com"])

    assert exit_code == 0
    user = db.scalar(select(User).where(User.email == "prompted@example.com"))
    assert user is not None
    assert "prompted-pw" not in capsys.readouterr().out


@pytest.mark.parametrize("argv", [[], ["--email", "boss@example.com", "--password"]])
def test_requires_email(db, argv):
    with pytest.raises(SystemExit):
        main(argv)
