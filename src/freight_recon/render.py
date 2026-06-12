"""PDF -> page images via PyMuPDF.

Vision extraction works on rasterized pages, so we render each page to a PNG at
a configurable DPI. Higher DPI = sharper small print (PRO numbers, line-item
amounts) at the cost of larger payloads; 200 DPI is a good default for invoices.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class PageImage:
    """A single rendered page, ready to hand to a vision model."""

    page_number: int  # 1-based
    png_bytes: bytes

    @property
    def base64(self) -> str:
        return base64.standard_b64encode(self.png_bytes).decode("ascii")

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.write_bytes(self.png_bytes)
        return path


def render_pdf(pdf_path: str | Path, dpi: int = 200, max_pages: int | None = None) -> list[PageImage]:
    """Render a PDF's pages to PNG images.

    Args:
        pdf_path: Path to the PDF on disk.
        dpi: Render resolution. 200 is a good default for freight invoices.
        max_pages: If set, render at most this many pages (invoices are usually 1-2).
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    images: list[PageImage] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc):
            if max_pages is not None and index >= max_pages:
                break
            pix = page.get_pixmap(dpi=dpi)
            images.append(PageImage(page_number=index + 1, png_bytes=pix.tobytes("png")))
    return images
