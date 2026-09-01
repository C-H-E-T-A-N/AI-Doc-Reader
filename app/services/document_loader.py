"""
PDF -> text extraction, using PyMuPDF (imported as `fitz`).

A PDF is not a text file: it's a page-description format. Each page is a
list of drawing instructions -- "put this glyph at this (x, y) using this
font" -- not a paragraph of text. A text-based PDF still carries enough
information (character codes + each font's glyph-to-character mapping)
for a library to reconstruct the text a human would read, roughly in
reading order. That's what `page.get_text()` does below.

A *scanned* PDF has no such information: each page is just a raster image
(a photograph/scan) with no attached text layer, so get_text() returns an
empty string -- not an error. Recovering text from that requires OCR
(Optical Character Recognition, e.g. Tesseract), which is a genuinely
different problem (pixels -> text, not structured-data -> text) and is
out of scope for this stage. We detect the zero-text case and raise
instead of silently returning an empty document.
"""

from dataclasses import dataclass

import fitz  # PyMuPDF


class PDFExtractionError(Exception):
    """Raised when a PDF can't be opened, is encrypted, or has no extractable text."""


@dataclass
class PageText:
    page_number: int  # 1-indexed, matching how humans refer to pages
    text: str


@dataclass
class ExtractedDocument:
    pages: list[PageText]
    total_pages: int
    total_characters: int


def extract_text(file_path: str) -> ExtractedDocument:
    """Open a PDF and extract per-page text. Raises PDFExtractionError on failure."""
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        raise PDFExtractionError(f"Could not open PDF: {e}") from e

    try:
        if doc.is_encrypted:
            raise PDFExtractionError("PDF is password-protected and cannot be read.")

        if doc.page_count == 0:
            raise PDFExtractionError("PDF has no pages.")

        pages: list[PageText] = []
        total_characters = 0
        for index, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            pages.append(PageText(page_number=index, text=text))
            total_characters += len(text)
    finally:
        doc.close()

    if total_characters == 0:
        raise PDFExtractionError(
            "No extractable text found in this PDF. It may contain only "
            "scanned images -- OCR would be required, which this version "
            "does not support."
        )

    return ExtractedDocument(
        pages=pages,
        total_pages=len(pages),
        total_characters=total_characters,
    )
