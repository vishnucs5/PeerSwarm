"""
PDF reader tool for extracting text from PDF documents.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)


class PDFReaderTool:
    """Tool for reading and extracting text from PDFs."""

    def __init__(self, max_chars: int = 50000):
        self.max_chars = max_chars

    def read_file(self, path: str | Path) -> str | None:
        """Read text from a local PDF file."""
        path = Path(path)
        if not path.exists():
            logger.error(f"PDF file not found: {path}")
            return None

        try:
            text = self._extract_from_path(path)
            if text:
                text = text[:self.max_chars]
            logger.info(f"Read PDF {path.name}: {len(text)} chars")
            return text
        except Exception as e:
            logger.error(f"Error reading PDF {path}: {e}")
            return None

    def read_url(self, url: str) -> str | None:
        """Read text from a PDF at a URL."""
        try:
            response = requests.get(url, timeout=60, stream=True)
            response.raise_for_status()
            content = response.content
            text = self._extract_from_bytes(content, url)
            if text:
                text = text[:self.max_chars]
            logger.info(f"Read PDF from {url[:80]}: {len(text)} chars")
            return text
        except Exception as e:
            logger.error(f"Error reading PDF from URL {url[:80]}: {e}")
            return None

    def read_bytes(self, data: bytes, source: str = "unknown") -> str | None:
        """Read text from PDF bytes."""
        try:
            text = self._extract_from_bytes(data, source)
            if text:
                text = text[:self.max_chars]
            return text
        except Exception as e:
            logger.error(f"Error reading PDF bytes: {e}")
            return None

    def _extract_with_backends(self, open_fn) -> str | None:
        """Try PDF backends in order using the provided opener."""
        for mod_name in ("fitz", "pdfplumber"):
            try:
                lib = __import__(mod_name)
                doc = open_fn(lib)
                if mod_name == "fitz":
                    text_parts = []
                    for page in doc:
                        text_parts.append(page.get_text())
                    doc.close()
                    return "\n".join(text_parts)
                else:
                    with doc as pdf:
                        text_parts = [page.extract_text() or "" for page in pdf.pages]
                    return "\n".join(text_parts)
            except ImportError:
                continue

        logger.error("No PDF reader available (install pymupdf or pdfplumber)")
        return None

    def _extract_from_path(self, path: Path) -> str | None:
        """Extract text using PyMuPDF or pdfplumber."""
        return self._extract_with_backends(lambda lib: lib.open(str(path)))

    def _extract_from_bytes(self, data: bytes, source: str) -> str | None:
        """Extract text from PDF bytes."""
        return self._extract_with_backends(
            lambda lib: lib.open(stream=data, filetype="pdf")
            if lib.__name__ == "fitz"
            else lib.open(BytesIO(data))
        )

    def extract_metadata(self, path: str | Path) -> dict[str, Any]:
        """Extract metadata from a PDF."""
        path = Path(path)
        if not path.exists():
            return {}

        try:
            import fitz
            doc = fitz.open(str(path))
            metadata = doc.metadata or {}
            metadata["pages"] = len(doc)
            metadata["file_size"] = path.stat().st_size
            doc.close()
            return metadata
        except ImportError:
            return {"pages": 0, "file_size": path.stat().st_size}
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return {}

    def extract_sections(self, content: str) -> dict[str, str]:
        """Split PDF content into sections by headings."""
        sections = {}
        current_section = "preamble"
        current_lines = []

        for line in content.split("\n"):
            stripped = line.strip()
            if stripped and len(stripped) < 200 and stripped.isupper() or stripped.endswith(":"):
                if current_lines:
                    sections[current_section] = "\n".join(current_lines)
                    current_lines = []
                current_section = stripped.lower().replace(" ", "_").replace(":", "")
            else:
                current_lines.append(line)

        if current_lines:
            sections[current_section] = "\n".join(current_lines)

        return sections


_pdf_reader_tool: PDFReaderTool | None = None


def get_pdf_reader_tool() -> PDFReaderTool:
    global _pdf_reader_tool
    if _pdf_reader_tool is None:
        _pdf_reader_tool = PDFReaderTool()
    return _pdf_reader_tool
