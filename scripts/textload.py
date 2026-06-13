"""Load plain text from an input file — worker module.

Keeps input handling separate from extraction: methods call load_text() and get
a string, regardless of whether the source was .txt or .pdf.

    .pdf  -> extracted with `pdftotext` (poppler; lightweight, already a system dep)
    other -> read as UTF-8 text

No CLI here by design — see the top-level cli.py wrapper.
"""

import re
import shutil
import subprocess
from pathlib import Path

# C0 control chars that are invalid in XML 1.0 (everything except tab/newline/CR).
# pdftotext emits form-feed (\x0c) at page breaks; if such a char reaches a node
# label it produces an unparseable SVG ("PCDATA invalid Char value 12").
_INVALID_XML_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def load_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        text = _pdf_to_text(path)
    else:
        text = path.read_text(encoding="utf-8")
    # Replace control chars with spaces so downstream RDF/DOT/SVG stays valid.
    return _INVALID_XML_CTRL.sub(" ", text)


def _pdf_to_text(path: Path) -> str:
    if shutil.which("pdftotext") is None:
        raise RuntimeError(
            "pdftotext not found — install poppler: sudo apt-get install -y poppler-utils"
        )
    # '-' sends extracted text to stdout; default (no -layout) gives reading-order
    # flow, which parses into sentences better than column-preserving layout.
    result = subprocess.run(
        ["pdftotext", str(path), "-"],
        check=True, capture_output=True, text=True,
    )
    return result.stdout
