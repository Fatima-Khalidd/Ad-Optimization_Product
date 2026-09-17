"""Create an admin user.

Admins exist only because this script created them - /api/auth/signup can never make one
(docs/PLAN.md section 5). This is the only path that writes role="admin".

Run it from the backend/ directory, either as a module:

    .venv/Scripts/python -m scripts.create_admin --email you@example.com --password change-me-now

or as a file:

    .venv/Scripts/python scripts/create_admin.py --email you@example.com --password change-me-now

Omit --password to be prompted for it (no echo) instead of putting it on the command line,
where it would land in shell history.

Exit codes: 0 created, 2 bad input (duplicate email, invalid email, or password shorter than
8 characters). argparse itself exits 2 for missing/malformed arguments.
"""

import argparse
import sys
from getpass import getpass
from pathlib import Path

# Allow running the file directly (python scripts/create_admin.py) without installing the app.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import EmailStr, TypeAdapter, ValidationError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.db import get_engine  # noqa: E402
from app.services.auth import EmailTakenError, create_admin  # noqa: E402

MIN_PASSWORD_LENGTH = 8
_EMAIL_ADAPTER = TypeAdapter(EmailStr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create an admin user.")
    parser.add_argument("--email", required=True, help="Login email for the admin.")
    parser.add_argument(
        "--password",
        default=None,
        help="At least 8 characters. Omit to be prompted for it instead (recommended).",
    )
    args = parser.parse_args(argv)

    password = args.password if args.password is not None else getpass("Password: ")

    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"error: password must be at least {MIN_PASSWORD_LENGTH} characters", file=sys.stderr)
        return 2

    try:
        email = str(_EMAIL_ADAPTER.validate_python(args.email))
    except ValidationError:
        print(f"error: {args.email!r} is not a valid email address", file=sys.stderr)
        return 2

    with Session(get_engine()) as session:
        try:
            user = create_admin(session, email, password)
        except EmailTakenError:
            print(f"error: {email.strip().lower()} is already registered", file=sys.stderr)
            return 2
        print(f"created admin {user.email} (id={user.id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
