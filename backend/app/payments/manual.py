"""Manual payments: the client pays from their own wallet/bank app and reports the transaction ID.

Nothing here moves money or marks an invoice paid — see app/services/payments.py for the
admin-only confirmation step (docs/PLAN.md section 6, Stage 7, Rules).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Invoice, Payment, PaymentMethod
from app.payments.base import PaymentInstruction
from app.services.storage import get_storage

if TYPE_CHECKING:  # import-cycle guard, see app/payments/base.py
    from sqlalchemy.orm import Session

    from app.models import Client
    from app.schemas.billing import PaymentSubmission


class ManualProvider:
    name = "manual"

    def instructions_for(self, session: Session, invoice: Invoice) -> list[PaymentInstruction]:
        methods = session.scalars(
            select(PaymentMethod)
            .where(PaymentMethod.is_active.is_(True))
            .order_by(PaymentMethod.sort_order, PaymentMethod.id)
        ).all()
        return [
            PaymentInstruction(
                method_type=method.type,
                account_title=method.account_title,
                account_identifier=method.account_identifier,
                instructions=method.instructions,
            )
            for method in methods
        ]

    def submit(
        self,
        session: Session,
        client: Client,
        invoice: Invoice,
        submission: PaymentSubmission,
        proof: bytes | None = None,
        proof_ext: str | None = None,
    ) -> Payment:
        payment = Payment(
            invoice_id=invoice.id,
            client_id=client.id,
            method_type=submission.method_type,
            transaction_ref=submission.transaction_ref.strip(),
            amount=submission.amount,
            paid_at=submission.paid_at,
            status="pending",
            provider=self.name,
        )
        session.add(payment)
        try:
            # uq_payments_method_ref is the single source of truth for "already used".
            session.flush()
        except IntegrityError:
            session.rollback()
            raise HTTPException(
                status_code=409,
                detail="this transaction id has already been submitted for this payment method",
            ) from None

        if proof is not None and proof_ext is not None:
            payment.proof_file_path = get_storage().save(
                f"proofs/{client.id}/{payment.id}.{proof_ext}", proof
            )

        invoice.status = "payment_submitted"
        session.commit()
        session.refresh(payment)
        return payment
