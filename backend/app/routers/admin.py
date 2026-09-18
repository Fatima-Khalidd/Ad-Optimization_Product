"""/api/admin — operator routes. Every one of them is gated by CurrentAdmin."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.deps import CurrentAdmin
from app.core.errors import NotFoundError
from app.models import Client, Invoice, Payment
from app.schemas.admin import (
    AdminClientOut,
    AdminInvoiceOut,
    AuditLogOut,
    ClientPatch,
    ConfirmInvoiceIn,
    InvoiceDraftIn,
    IssueInvoiceIn,
    ReviewIn,
    RunAdminOut,
    VoidInvoiceIn,
)
from app.schemas.billing import (
    AdminPaymentOut,
    PaymentMethodIn,
    PaymentMethodOut,
    PaymentMethodPatch,
    RejectRequest,
    ReviewRequest,
    admin_payment_out,
)
from app.services import admin as admin_service
from app.services import audit as audit_service
from app.services import billing as billing_service
from app.services import payments as payments_service
from app.services.storage import get_storage

router = APIRouter(prefix="/api/admin", tags=["admin"])

ReviewStatus = Literal["pending", "approved", "rejected"]
InvoiceStatus = Literal["draft", "issued", "payment_submitted", "paid", "void"]


@router.get("/clients", response_model=list[AdminClientOut])
def list_clients(actor: CurrentAdmin, session: Session = Depends(get_session)):
    return admin_service.list_clients(session)


@router.get("/clients/{client_id}", response_model=AdminClientOut)
def get_client(client_id: int, actor: CurrentAdmin, session: Session = Depends(get_session)):
    return admin_service.get_client(session, client_id)


@router.patch("/clients/{client_id}", response_model=AdminClientOut)
def update_client(
    client_id: int,
    patch: ClientPatch,
    actor: CurrentAdmin,
    session: Session = Depends(get_session),
):
    return admin_service.update_client(session, actor, client_id, patch)


@router.get("/runs", response_model=list[RunAdminOut])
def list_runs(
    actor: CurrentAdmin,
    review_status: ReviewStatus | None = Query(default=None),
    session: Session = Depends(get_session),
):
    runs = admin_service.list_runs(session, review_status)
    # ONE extra query for every distinct client behind these runs, keyed by id, instead of
    # a session.get() per row inside serialize_run() — that keeps this endpoint's query
    # count flat regardless of how many runs are in the queue (no N+1; see
    # test_admin_api.py::test_the_queue_avoids_n_plus_1_client_lookups for the proof).
    client_ids = {run.client_id for run in runs}
    clients_by_id = {}
    if client_ids:
        clients_by_id = {
            c.id: c for c in session.scalars(select(Client).where(Client.id.in_(client_ids)))
        }
    return [
        admin_service.serialize_run(session, run, clients_by_id.get(run.client_id)) for run in runs
    ]


@router.post("/runs/{run_id}/approve", response_model=RunAdminOut)
def approve_run(
    run_id: int, body: ReviewIn, actor: CurrentAdmin, session: Session = Depends(get_session)
):
    run = admin_service.approve_run(session, actor, run_id, body.note)
    return admin_service.serialize_run(session, run)


@router.post("/runs/{run_id}/reject", response_model=RunAdminOut)
def reject_run(
    run_id: int, body: ReviewIn, actor: CurrentAdmin, session: Session = Depends(get_session)
):
    run = admin_service.reject_run(session, actor, run_id, body.note)
    return admin_service.serialize_run(session, run)


@router.get("/invoices", response_model=list[AdminInvoiceOut])
def list_invoices(
    actor: CurrentAdmin,
    client_id: int | None = Query(default=None),
    invoice_status: InvoiceStatus | None = Query(default=None, alias="status"),
    session: Session = Depends(get_session),
):
    invoices = billing_service.list_invoices(session, client_id=client_id, status=invoice_status)
    # Same shape as the runs queue: one extra query for every distinct client behind these
    # invoices, keyed by id, instead of a session.get() per row (no N+1).
    client_ids = {invoice.client_id for invoice in invoices}
    clients_by_id = {}
    if client_ids:
        clients_by_id = {
            c.id: c for c in session.scalars(select(Client).where(Client.id.in_(client_ids)))
        }
    return [
        billing_service.serialize_invoice(session, invoice, clients_by_id.get(invoice.client_id))
        for invoice in invoices
    ]


@router.post("/invoices", response_model=AdminInvoiceOut, status_code=status.HTTP_201_CREATED)
def draft_invoice(
    body: InvoiceDraftIn, actor: CurrentAdmin, session: Session = Depends(get_session)
):
    invoice = billing_service.draft_invoice(
        session, actor, body.client_id, body.period_start, body.period_end
    )
    return billing_service.serialize_invoice(session, invoice)


@router.post("/invoices/{invoice_id}/confirm", response_model=AdminInvoiceOut)
def confirm_invoice(
    invoice_id: int,
    body: ConfirmInvoiceIn,
    actor: CurrentAdmin,
    session: Session = Depends(get_session),
):
    invoice = billing_service.confirm_invoice(
        session, actor, invoice_id, body.confirmed_recovered_waste
    )
    return billing_service.serialize_invoice(session, invoice)


@router.post("/invoices/{invoice_id}/issue", response_model=AdminInvoiceOut)
def issue_invoice(
    invoice_id: int,
    body: IssueInvoiceIn,
    actor: CurrentAdmin,
    session: Session = Depends(get_session),
):
    invoice = billing_service.issue_invoice(session, actor, invoice_id, body.due_date)
    return billing_service.serialize_invoice(session, invoice)


@router.post("/invoices/{invoice_id}/void", response_model=AdminInvoiceOut)
def void_invoice(
    invoice_id: int,
    body: VoidInvoiceIn,
    actor: CurrentAdmin,
    session: Session = Depends(get_session),
):
    invoice = billing_service.void_invoice(session, actor, invoice_id, body.note)
    return billing_service.serialize_invoice(session, invoice)


@router.get("/audit-log", response_model=list[AuditLogOut])
def list_audit_log(
    actor: CurrentAdmin,
    limit: int = Query(default=200, ge=1, le=1000),
    entity_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return audit_service.list_entries(session, limit=limit, entity_type=entity_type, action=action)


# --------------------------------------------------------------------------- manual payments

# Reverse of payments_service.PROOF_TYPES: extension -> content type.
_PROOF_MEDIA = {
    extension: content_type
    for content_type, (extension, _magic) in payments_service.PROOF_TYPES.items()
}


def _payment_row(session: Session, payment: Payment) -> AdminPaymentOut:
    invoice = session.get(Invoice, payment.invoice_id)
    client = session.get(Client, payment.client_id)
    return admin_payment_out(payment, invoice, client)


@router.get("/payments", response_model=list[AdminPaymentOut])
def list_payments(
    actor: CurrentAdmin, status: str = "pending", session: Session = Depends(get_session)
):
    """?status=pending (the review queue, default) or ?status=all for the whole history."""
    rows = payments_service.list_pending_payments(session, None if status == "all" else status)
    return [admin_payment_out(row.payment, row.invoice, row.client) for row in rows]


@router.post("/payments/{payment_id}/confirm", response_model=AdminPaymentOut)
def confirm_payment(
    payment_id: int,
    body: ReviewRequest,
    actor: CurrentAdmin,
    session: Session = Depends(get_session),
):
    """The ONLY way money is marked as received (docs/PLAN.md section 6, Stage 7, Rules)."""
    payment = payments_service.confirm_payment(session, actor, payment_id, body.note)
    return _payment_row(session, payment)


@router.post("/payments/{payment_id}/reject", response_model=AdminPaymentOut)
def reject_payment(
    payment_id: int,
    body: RejectRequest,
    actor: CurrentAdmin,
    session: Session = Depends(get_session),
):
    payment = payments_service.reject_payment(session, actor, payment_id, body.note)
    return _payment_row(session, payment)


@router.get("/payments/{payment_id}/proof")
def get_payment_proof(
    payment_id: int, actor: CurrentAdmin, session: Session = Depends(get_session)
) -> Response:
    payment = session.get(Payment, payment_id)
    if payment is None or not payment.proof_file_path:
        raise NotFoundError("no proof file for this payment")
    extension = payment.proof_file_path.rsplit(".", 1)[-1].lower()
    key = f"proofs/{payment.client_id}/{payment.id}.{extension}"
    return Response(
        content=get_storage().read(key),
        media_type=_PROOF_MEDIA.get(extension, "application/octet-stream"),
        headers={"Content-Disposition": f'inline; filename="proof-{payment.id}.{extension}"'},
    )


# --------------------------------------------------------------------------- payment methods


@router.get("/payment-methods", response_model=list[PaymentMethodOut])
def list_payment_methods(actor: CurrentAdmin, session: Session = Depends(get_session)):
    """Admins see inactive accounts too, so they can switch one back on."""
    return payments_service.list_payment_methods(session, active_only=False)


@router.post("/payment-methods", response_model=PaymentMethodOut, status_code=201)
def create_payment_method(
    body: PaymentMethodIn, actor: CurrentAdmin, session: Session = Depends(get_session)
):
    return payments_service.create_payment_method(session, actor, body)


@router.patch("/payment-methods/{method_id}", response_model=PaymentMethodOut)
def update_payment_method(
    method_id: int,
    body: PaymentMethodPatch,
    actor: CurrentAdmin,
    session: Session = Depends(get_session),
):
    return payments_service.update_payment_method(session, actor, method_id, body)
