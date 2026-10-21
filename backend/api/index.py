"""Vercel's entry point. vercel.json rewrites every path here; Vercel serves `app` as ASGI."""

import sys
from pathlib import Path

# The function runs from api/, so the backend root (where the `app` package lives) is put
# on the import path explicitly rather than relying on the runtime's working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

__all__ = ["app"]
