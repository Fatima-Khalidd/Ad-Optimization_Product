"""/api/uploads — docs/PLAN.md section 5. The client_id always comes from the JWT."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.deps import CurrentClient
from app.core.errors import FileTooLargeError, InvalidUploadError
from app.core.settings import get_settings
from app.models import AdDataUpload
from app.schemas.uploads import UploadOut
from app.services.upload import create_upload, get_upload, list_uploads, template_csv

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

SessionDep = Annotated[Session, Depends(get_session)]

_CHUNK = 1024 * 1024


async def _read_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Read the upload a megabyte at a time and abort as soon as it goes over the limit.

    Reading in fixed-size chunks (rather than `await file.read()`) means an oversize upload
    never sits fully in memory before we notice: we stop and raise as soon as the running
    total crosses `max_bytes`, well before the whole body has been buffered.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_CHUNK):
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLargeError(f"file is larger than {max_bytes // (1024 * 1024)} MB")
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
    client: CurrentClient,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> AdDataUpload:
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    data = await _read_limited(file, max_bytes)
    upload = create_upload(session, client, file.filename or "upload.csv", data)
    if upload.status == "failed":
        raise InvalidUploadError(
            {
                "upload_id": upload.id,
                "status": upload.status,
                "errors": upload.validation_report.get("errors", []),
                "warnings": upload.validation_report.get("warnings", []),
            }
        )
    return upload


@router.get("", response_model=list[UploadOut])
def read_uploads(client: CurrentClient, session: SessionDep) -> list[AdDataUpload]:
    return list_uploads(session, client.id)


@router.get("/{upload_id}", response_model=UploadOut)
def read_upload(upload_id: int, client: CurrentClient, session: SessionDep) -> AdDataUpload:
    return get_upload(session, client.id, upload_id)
