"""POST /api/analyze/{upload_id} and GET /api/runs/{id} — docs/PLAN.md section 5."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.deps import CurrentClient
from app.core.errors import InvalidUploadError
from app.models import AnalysisRun
from app.schemas.reports import RunOut
from app.services.analysis import create_run, execute_run, get_run

router = APIRouter(prefix="/api", tags=["analysis"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/analyze/{upload_id}", status_code=202, response_model=RunOut)
def start_analysis(
    upload_id: int,
    background_tasks: BackgroundTasks,
    client: CurrentClient,
    session: SessionDep,
) -> AnalysisRun:
    try:
        run = create_run(session, client, upload_id)
    except ValueError as exc:
        # create_run raises a plain ValueError when client.config_overrides is corrupt
        # (Stage 6 validates on write, so this should be unreachable) - translated here
        # into a clean 422 rather than letting it fall through to a 500.
        raise InvalidUploadError(str(exc)) from exc
    # No Redis in the MVP (docs/PLAN.md section 0): FastAPI BackgroundTasks. The task opens
    # its own session, because this request's session is closed before it runs.
    background_tasks.add_task(execute_run, run.id)
    return run


@router.get("/runs/{run_id}", response_model=RunOut)
def read_run(run_id: int, client: CurrentClient, session: SessionDep) -> AnalysisRun:
    return get_run(session, client.id, run_id)
