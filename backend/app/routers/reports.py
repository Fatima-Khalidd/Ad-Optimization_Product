"""GET /api/reports/latest and /api/reports/{run_id} — approved runs only."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.deps import CurrentClient
from app.core.errors import NotFoundError
from app.schemas.reports import ReportOut
from app.services.analysis import get_report, latest_report
from app.services.pdf import build_report_pdf

router = APIRouter(prefix="/api/reports", tags=["reports"])

SessionDep = Annotated[Session, Depends(get_session)]


# Declared before "/{run_id}" so the literal path wins the match.
@router.get("/latest", response_model=ReportOut)
def read_latest_report(client: CurrentClient, session: SessionDep) -> ReportOut:
    report = latest_report(session, client.id)
    if report is None:
        raise NotFoundError("no approved report yet")
    return report


@router.get("/{run_id}", response_model=ReportOut)
def read_report(run_id: int, client: CurrentClient, session: SessionDep) -> ReportOut:
    return get_report(session, client.id, run_id)


@router.get("/{run_id}/pdf")
def report_pdf(run_id: int, client: CurrentClient, session: SessionDep) -> Response:
    """The dashboard's report as a downloadable PDF.

    get_report() is the only gate: it already 404s unless the run is done AND approved, and for
    another tenant's run. Do not add a second check here — two gates drift apart.
    """
    report = get_report(session, client.id, run_id)
    pdf = build_report_pdf(report, client.business_name)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ad-waste-report-{run_id}.pdf"',
            "Cache-Control": "no-store",
        },
    )
