"""The seam between billing and however the money actually arrives.

`ManualProvider` (this stage) records a transaction ID the client typed in after paying from
their own wallet or bank app. An automatic gateway later (docs/PLAN.md section 9) is a NEW class
implementing this Protocol — nothing in app/services or app/routers changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:  # import-cycle guard: app.schemas.billing imports PaymentInstruction from here
    from sqlalchemy.orm import Session

    from app.models import Client, Invoice, Payment
    from app.schemas.billing import PaymentSubmission


class PaymentInstruction(BaseModel):
    """One account a client can pay into. Rendered on the billing page and in the invoice PDF."""

    method_type: str
    account_title: str
    account_identifier: str
    instructions: str | None = None


@runtime_checkable
class PaymentProvider(Protocol):
    """Everything billing needs to know about a way of taking money."""

    name: str

    def instructions_for(self, session: Session, invoice: Invoice) -> list[PaymentInstruction]:
        """The accounts to show on this invoice, in display order."""
        ...

    def submit(
        self,
        session: Session,
        client: Client,
        invoice: Invoice,
        submission: PaymentSubmission,
        proof: bytes | None,
        proof_ext: str | None,
    ) -> Payment:
        """Record a client's claim that they paid.

        NEVER marks the invoice paid — only an admin does.
        """
        ...
