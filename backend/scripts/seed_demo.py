"""Seed a demo client with a finished, approved report, for sales demos.

Idempotent: every object is looked up before it is created, so running this twice
leaves exactly one demo client, one upload and one approved run.

Refuses to run when ENV=prod: a demo client with a shared password is a real hazard
in a production database, and this script must never be the thing that creates one.

    cd backend
    DEMO_PASSWORD='a-strong-password' python -m scripts.seed_demo
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.core.settings import get_settings
from app.models import AdDataUpload, AnalysisRun, Client, User
from app.pipeline.data_generator import write_sample_csv
from app.services.admin import approve_run
from app.services.analysis import create_run, execute_run
from app.services.auth import create_admin, signup_client
from app.services.upload import DuplicateUploadError, create_upload

DEMO_EMAIL = os.environ.get("DEMO_EMAIL", "demo@example.com")
ADMIN_EMAIL = os.environ.get("DEMO_ADMIN_EMAIL", "admin@example.com")
BUSINESS_NAME = "Demo Retail Co"
SAMPLE_FILENAME = "sample_30d.csv"
APPROVAL_NOTE = "Seeded demo data."


def _get_or_create_demo_client(session: Session, password: str) -> Client:
    user = session.scalars(select(User).where(User.email == DEMO_EMAIL)).one_or_none()
    if user is None:
        user = signup_client(session, DEMO_EMAIL, password, BUSINESS_NAME)
        session.commit()
        print(f"created demo client {DEMO_EMAIL}")
    else:
        print(f"demo client {DEMO_EMAIL} already exists")
    return session.scalars(select(Client).where(Client.user_id == user.id)).one()


def _get_or_create_admin(session: Session, password: str) -> User:
    admin = session.scalars(select(User).where(User.email == ADMIN_EMAIL)).one_or_none()
    if admin is None:
        admin = create_admin(session, ADMIN_EMAIL, password)
        session.commit()
        print(f"created admin {ADMIN_EMAIL}")
    else:
        print(f"admin {ADMIN_EMAIL} already exists")
    return admin


def _sample_csv_bytes() -> bytes:
    """A 30-day synthetic account with injected waste, so the demo report has real numbers."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / SAMPLE_FILENAME
        write_sample_csv(
            path,
            days=30,
            seed=20260916,
            waste={"placement": {"audience_network": 3.0}},
        )
        return path.read_bytes()


def _get_or_create_upload(session: Session, client: Client) -> AdDataUpload:
    try:
        upload = create_upload(session, client, SAMPLE_FILENAME, _sample_csv_bytes())
        session.commit()
        print(f"uploaded {SAMPLE_FILENAME} ({upload.row_count} rows)")
        return upload
    except DuplicateUploadError:
        session.rollback()
        upload = session.scalars(
            select(AdDataUpload)
            .where(AdDataUpload.client_id == client.id)
            .order_by(AdDataUpload.id)
        ).first()
        assert upload is not None  # DuplicateUploadError means one exists
        print(f"upload {SAMPLE_FILENAME} already exists")
        return upload


def _get_or_create_approved_run(
    session: Session, client: Client, upload_id: int, admin: User
) -> AnalysisRun:
    existing = session.scalars(
        select(AnalysisRun).where(AnalysisRun.client_id == client.id).order_by(AnalysisRun.id)
    ).first()
    if existing is not None:
        print(f"run {existing.id} already exists ({existing.status}/{existing.review_status})")
        return existing

    run = create_run(session, client, upload_id)
    session.commit()
    run_id = run.id

    # Synchronous on purpose: the script must not exit before the analysis is written.
    execute_run(run_id)

    session.expire_all()
    run = session.get(AnalysisRun, run_id)
    assert run is not None
    if run.status != "done":
        raise RuntimeError(f"analysis run {run_id} finished as {run.status}: {run.error_message}")

    approve_run(session, admin, run_id, APPROVAL_NOTE)
    session.commit()
    print(f"run {run_id} analysed and approved (headline waste {run.headline_waste})")
    return run


def main() -> int:
    settings = get_settings()
    if settings.env == "prod":
        print(
            "ENV=prod. Refusing to seed a demo client into a production database.",
            file=sys.stderr,
        )
        return 2

    password = os.environ.get("DEMO_PASSWORD")
    if not password:
        print(
            "DEMO_PASSWORD is not set. Refusing to seed accounts with a guessable password.",
            file=sys.stderr,
        )
        return 2

    with Session(get_engine()) as session:
        admin = _get_or_create_admin(session, password)
        client = _get_or_create_demo_client(session, password)
        upload = _get_or_create_upload(session, client)
        _get_or_create_approved_run(session, client, upload.id, admin)

    print(f"done. Sign in as {DEMO_EMAIL} to see an approved report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
