"""/api/uploads — docs/PLAN.md section 5. The client_id always comes from the JWT."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.deps import CurrentClient
from app.core.errors import FileTooLargeError, InvalidUploadError
from app.core.settings import get_settings
from app.models import AdDataUpload
from app.schemas.uploads import UploadOut, UploadRejected
from app.services.upload import create_upload, get_upload, list_uploads, template_csv

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

SessionDep = Annotated[Session, Depends(get_session)]

_CHUNK = 1024 * 1024
# Allowance for multipart boundary/header overhead around the file part itself, so a
# Content-Length that is only slightly over the raw file limit isn't rejected unfairly.
_MULTIPART_OVERHEAD = 8192


def _too_large(max_bytes: int) -> FileTooLargeError:
    mb = max_bytes // (1024 * 1024)
    return FileTooLargeError({"message": f"file is larger than {mb} MB", "max_upload_mb": mb})


def _reject_by_content_length(request: Request, max_bytes: int) -> None:
    """Reject an obviously-oversize body before FastAPI parses the multipart form.

    By the time our route handler runs, Starlette has already received and spooled the
    whole request body (to memory or a temp file, per its own spooling threshold) - the
    chunked read below does not avoid that. What this check *does* avoid is asking
    Starlette/python-multipart to parse an obviously-oversize body into an UploadFile at
    all: a well-formed Content-Length header tells us to reject immediately. A missing or
    unparseable header (e.g. chunked transfer-encoding) falls through to the chunked read,
    which still bounds how much of the file we copy into our own `bytes` buffer.
    """
    raw = request.headers.get("content-length")
    if raw is None:
        return
    try:
        length = int(raw)
    except ValueError:
        return
    if length > max_bytes + _MULTIPART_OVERHEAD:
        raise _too_large(max_bytes)


async def _read_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Read the upload a megabyte at a time and abort as soon as it goes over the limit.

    Reading in fixed-size chunks (rather than `await file.read()`) bounds how much of the
    upload we copy into our own memory as a `bytes` object - it does not affect how much
    Starlette has already spooled internally, which is governed by its own spooling
    threshold. `_reject_by_content_length` is what avoids reading an obviously-oversize
    body at all; this loop is the fallback for requests without a usable Content-Length.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_CHUNK):
        total += len(chunk)
        if total > max_bytes:
            raise _too_large(max_bytes)
        chunks.append(chunk)
    return b"".join(chunks)


# Declared before "/{upload_id}" so the literal path wins the match.
@router.get("/template.csv")
def download_template() -> Response:
    return Response(
        content=template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ad-data-template.csv"'},
    )


@router.post("", status_code=201, response_model=UploadOut)
async def upload_file(
    request: Request,
    client: CurrentClient,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> AdDataUpload:
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    _reject_by_content_length(request, max_bytes)
    data = await _read_limited(file, max_bytes)
    try:
        upload = create_upload(session, client, file.filename or "upload.csv", data)
    except ValueError as exc:
        # create_upload raises a plain ValueError when client.config_overrides is corrupt
        # (Stage 6 validates on write, so this should be unreachable) - translated here
        # into a clean 422 rather than letting it fall through to a 500, mirroring
        # app/routers/analysis.py's identical guard around create_run.
        raise InvalidUploadError(str(exc)) from exc
    if upload.status == "failed":
        raise InvalidUploadError(
            UploadRejected(
                upload_id=upload.id,
                status=upload.status,
                errors=upload.validation_report.get("errors", []),
                warnings=upload.validation_report.get("warnings", []),
            ).model_dump()
        )
    return upload


@router.get("", response_model=list[UploadOut])
def read_uploads(client: CurrentClient, session: SessionDep) -> list[AdDataUpload]:
    return list_uploads(session, client.id)


@router.get("/{upload_id}", response_model=UploadOut)
def read_upload(upload_id: int, client: CurrentClient, session: SessionDep) -> AdDataUpload:
    return get_upload(session, client.id, upload_id)
