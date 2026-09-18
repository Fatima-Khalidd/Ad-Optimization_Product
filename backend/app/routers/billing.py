"""Client-facing billing. docs/PLAN.md section 5, "Billing".

Never accepts a client_id from the request — it always comes from CurrentClient.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated

import pydantic
from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.deps import CurrentClient
from app.core.errors import ValidationError
from app.core.settings import get_settings
from app.payments import get_payment_provider
from app.schemas.billing import (
    InvoiceOut,
    MethodType,
    PaymentMethodOut,
    PaymentOut,
    PaymentSubmission,
    invoice_out,
)
from app.services import payments as payments_service

router = APIRouter(prefix="/api/billing", tags=["billing"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/invoices", response_model=list[InvoiceOut])
def list_invoices(client: CurrentClient, session: SessionDep) -> list[InvoiceOut]:
    return [invoice_out(invoice) for invoice in payments_service.list_invoices(session, client.id)]


@router.get("/payment-methods", response_model=list[PaymentMethodOut])
def list_payment_methods(client: CurrentClient, session: SessionDep):
    return payments_service.list_payment_methods(session, active_only=True)


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, client: CurrentClient, session: SessionDep) -> InvoiceOut:
    invoice = payments_service.get_invoice(session, client.id, invoice_id)
    return invoice_out(
        invoice,
        payments_service.list_payments(session, invoice.id),
        get_payment_provider().instructions_for(session, invoice),
    )


@router.get("/invoices/{invoice_id}/pdf")
def get_invoice_pdf(invoice_id: int, client: CurrentClient, session: SessionDep) -> Response:
    invoice = payments_service.get_invoice(session, client.id, invoice_id)
    pdf = payments_service.build_invoice_pdf(
        invoice, client, get_payment_provider().instructions_for(session, invoice)
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'},
    )


@router.post("/invoices/{invoice_id}/payments", response_model=PaymentOut, status_code=201)
async def submit_payment(
    invoice_id: int,
    client: CurrentClient,
    session: SessionDep,
    method_type: Annotated[MethodType, Form()],
    transaction_ref: Annotated[str, Form(min_length=1, max_length=80)],
    amount: Annotated[Decimal, Form(gt=0, max_digits=14, decimal_places=2)],
    paid_at: Annotated[date, Form()],
    proof: Annotated[UploadFile | None, File()] = None,
):
    """The client reports a payment they already made. This NEVER marks the invoice paid."""
    invoice = payments_service.get_invoice(session, client.id, invoice_id)
    payments_service.ensure_payable(invoice)

    # The Form() annotations above mirror PaymentSubmission's own constraints (including
    # amount's max_digits/decimal_places), so this should not raise. It is wrapped anyway so the
    # two schemas can never again drift into a bare pydantic.ValidationError escaping as a 500.
    try:
        submission = PaymentSubmission(
            method_type=method_type,
            transaction_ref=transaction_ref,
            amount=amount,
            paid_at=paid_at,
        )
    except pydantic.ValidationError as exc:
        raise ValidationError(f"invalid payment submission: {exc}") from exc

    # Proof is validated (413/415) BEFORE the provider writes anything to the DB or storage, so
    # a rejected upload never leaves a half-made payment behind.
    data: bytes | None = None
    extension: str | None = None
    if proof is not None and proof.filename:
        data = await proof.read()
        extension = payments_service.validate_proof(
            proof.content_type, data, get_settings().max_proof_mb
        )

    return get_payment_provider().submit(session, client, invoice, submission, data, extension)
