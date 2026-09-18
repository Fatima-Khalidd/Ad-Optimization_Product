from decimal import Decimal
from io import BytesIO

from pypdf import PdfReader

from app.payments.base import PaymentInstruction
from app.services.payments import build_invoice_pdf
from tests.api.helpers import make_client, make_invoice

INSTRUCTIONS = [
    PaymentInstruction(
        method_type="jazzcash",
        account_title="Ali Raza",
        account_identifier="0300-1234567",
        instructions="JazzCash app -> Send Money -> Mobile Account.",
    ),
    PaymentInstruction(
        method_type="bank_iban",
        account_title="Ali Raza",
        account_identifier="PK36SCBL0000001123456702",
        instructions=None,
    ),
]


def _text(pdf: bytes) -> str:
    """Flatten page 1 to one whitespace-normalised line so line wrapping can't break an assert."""
    return " ".join(PdfReader(BytesIO(pdf)).pages[0].extract_text().split())


def test_the_pdf_shows_the_numbers_the_client_is_being_charged(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)

    pdf = build_invoice_pdf(invoice, client, INSTRUCTIONS)

    assert pdf.startswith(b"%PDF-")
    text = _text(pdf)
    assert "INV-2026-0001" in text
    assert "Karachi Kicks" in text
    assert "01 Sep 2026" in text and "30 Sep 2026" in text  # the billing period
    assert "07 Oct 2026" in text  # the due date
    assert "Rs. 15,000.00" in text  # base fee
    assert "Rs. 23,000.00" in text  # confirmed recovered waste, shown on the fee line
    assert "Rs. 4,600.00" in text  # performance fee
    assert "Rs. 19,600.00" in text  # total


def test_the_pdf_lists_every_account_and_asks_for_the_transaction_id(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)

    text = _text(build_invoice_pdf(invoice, client, INSTRUCTIONS))

    assert "JazzCash" in text
    assert "0300-1234567" in text
    assert "Bank transfer (IBAN)" in text
    assert "PK36SCBL0000001123456702" in text
    assert "JazzCash app -> Send Money -> Mobile Account." in text
    assert "reply with your transaction ID on the billing page" in text


def test_a_partly_paid_invoice_shows_the_balance(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client, amount_paid=Decimal("10000.00"))

    text = _text(build_invoice_pdf(invoice, client, INSTRUCTIONS))

    assert "Already paid" in text
    assert "Rs. 10,000.00" in text
    assert "Rs. 9,600.00" in text  # 19,600 - 10,000


def test_the_pdf_still_renders_when_no_accounts_are_configured(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)

    text = _text(build_invoice_pdf(invoice, client, []))

    assert "No payment accounts are set up yet" in text
    assert "Rs. 19,600.00" in text
