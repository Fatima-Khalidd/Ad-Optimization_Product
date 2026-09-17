"""Turn uploaded bytes into an AdDataUpload row: hash, store, validate, summarise."""

import hashlib
import io
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DuplicateUploadError, FileTooLargeError, NotFoundError
from app.core.settings import get_settings
from app.models import AdDataUpload, Client
from app.pipeline.config import REQUIRED_COLUMNS, PipelineConfig
from app.pipeline.loader import RowIssue, load_csv
from app.services.storage import get_storage

# Three rows a real Meta or Google export could plausibly contain. Served by
# GET /api/uploads/template.csv (docs/PLAN.md section 1 #3).
_TEMPLATE_ROWS = (
    "2026-08-01,CAMP-1,facebook_feed,25-34,male,mobile,morning,12500.00,420000,8400,168,420000",
    "2026-08-01,CAMP-1,instagram_stories,18-24,female,mobile,evening,7300.50,210000,3900,52,130000",
    "2026-08-02,CAMP-1,audience_network,35-44,male,tablet,night,9800.00,380000,5100,12,30000",
)

# The model column is `String(255)`; user-controlled filenames are truncated to fit rather
# than rejected outright.
_MAX_FILENAME_LEN = 255


def template_csv() -> bytes:
    lines = [",".join(REQUIRED_COLUMNS), *_TEMPLATE_ROWS]
    return ("\n".join(lines) + "\n").encode("utf-8")


def storage_key(client_id: int, digest: str) -> str:
    return f"uploads/{client_id}/{digest}.csv"


def create_upload(session: Session, client: Client, filename: str, data: bytes) -> AdDataUpload:
    """Store the bytes and record the row.

    Never raises on a bad CSV: the row is kept with status "failed" and a row-level
    validation report, so the UI can point at the exact bad lines. Only the size check
    (before anything is hashed, parsed or written) and the duplicate check can raise.
    """
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise FileTooLargeError(
            {
                "message": f"file exceeds the {get_settings().max_upload_mb}MB limit",
                "max_upload_mb": get_settings().max_upload_mb,
            }
        )

    digest = hashlib.sha256(data).hexdigest()
    existing = session.scalars(
        select(AdDataUpload).where(
            AdDataUpload.client_id == client.id, AdDataUpload.file_sha256 == digest
        )
    ).first()
    if existing is not None:
        raise DuplicateUploadError(
            {"message": "this file has already been uploaded", "upload_id": existing.id}
        )

    config = PipelineConfig.from_overrides(client.config_overrides or {})
    try:
        # Decode ourselves rather than handing raw bytes to load_csv: pandas/the loader
        # treats a bad decode as a whole-file RowIssue rather than raising, which would
        # bypass this except clause and its uniform "could not read" wording.
        text = data.decode("utf-8")
        result = load_csv(io.StringIO(text), config)
        errors = list(result.errors)
        warnings = list(result.warnings)
        row_count = result.row_count
        date_range = result.date_range
    except Exception as exc:  # noqa: BLE001 - a binary or unreadable file must not 500 the request
        errors = [RowIssue(None, None, f"could not read the file as CSV: {exc}")]
        warnings = []
        row_count = 0
        date_range = None

    key = get_storage().save(storage_key(client.id, digest), data)
    start, end = date_range if date_range else (None, None)

    upload = AdDataUpload(
        client_id=client.id,
        original_filename=filename[:_MAX_FILENAME_LEN],
        file_path=key,
        file_sha256=digest,
        row_count=row_count,
        date_range_start=start,
        date_range_end=end,
        status="validated" if not errors else "failed",
        validation_report={
            "errors": [asdict(issue) for issue in errors],
            "warnings": [asdict(issue) for issue in warnings],
        },
    )
    session.add(upload)
    session.commit()
    session.refresh(upload)
    return upload


def list_uploads(session: Session, client_id: int) -> list[AdDataUpload]:
    return list(
        session.scalars(
            select(AdDataUpload)
            .where(AdDataUpload.client_id == client_id)
            .order_by(AdDataUpload.uploaded_at.desc(), AdDataUpload.id.desc())
        )
    )


def get_upload(session: Session, client_id: int, upload_id: int) -> AdDataUpload:
    upload = session.scalars(
        select(AdDataUpload).where(
            AdDataUpload.id == upload_id, AdDataUpload.client_id == client_id
        )
    ).first()
    if upload is None:
        raise NotFoundError("upload not found")
    return upload
