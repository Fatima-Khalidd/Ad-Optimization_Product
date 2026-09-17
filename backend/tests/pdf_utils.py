"""Read a generated PDF back as text, so tests can assert on what a client would actually see."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def pdf_text(data: bytes) -> str:
    """All pages' text with every run of whitespace collapsed to one space.

    Collapsing matters: ReportLab wraps paragraphs, so a sentence can be split across lines in
    the PDF's text stream. Tests assert on the collapsed string, never on raw extraction.
    """
    reader = PdfReader(BytesIO(data))
    raw = " ".join(page.extract_text() or "" for page in reader.pages)
    return " ".join(raw.split())


def pdf_page_count(data: bytes) -> int:
    return len(PdfReader(BytesIO(data)).pages)


def pdf_page_texts(data: bytes) -> list[str]:
    """Per-page collapsed text — used to prove a long table repeats its header row."""
    reader = PdfReader(BytesIO(data))
    return [" ".join((page.extract_text() or "").split()) for page in reader.pages]
