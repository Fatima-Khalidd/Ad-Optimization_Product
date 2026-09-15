"""Import every model so Base.metadata knows all tables (Alembic autogenerate relies on this)."""

from app.models.analysis import AnalysisRun, Recommendation, SegmentMetric, WasteReport
from app.models.audit import AuditLog
from app.models.billing import Invoice, Payment, PaymentMethod
from app.models.client import Client
from app.models.upload import AdDataUpload
from app.models.user import User

__all__ = [
    "AdDataUpload",
    "AnalysisRun",
    "AuditLog",
    "Client",
    "Invoice",
    "Payment",
    "PaymentMethod",
    "Recommendation",
    "SegmentMetric",
    "User",
    "WasteReport",
]
