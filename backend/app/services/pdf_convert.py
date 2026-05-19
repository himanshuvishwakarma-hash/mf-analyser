"""Convert .docx bytes to PDF using LibreOffice headless.

Requires `soffice` (or `libreoffice`) in PATH. The Docker image installs it
via apt-get; OPS_RUNBOOK documents the host requirement for non-Docker runs.

If soffice is missing, raise PdfConvertError so the API can return a clear
503 instead of a generic 500.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


class PdfConvertError(RuntimeError):
    """Raised when LibreOffice is unavailable or conversion fails."""


def _soffice_path() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def docx_to_pdf(docx_bytes: bytes, *, timeout_sec: int = 60) -> bytes:
    """Convert docx bytes to pdf bytes. Uses a per-call temp dir."""
    bin_path = _soffice_path()
    if not bin_path:
        raise PdfConvertError(
            "LibreOffice (soffice) is not installed. "
            "Install via `apt-get install libreoffice` or run in the Docker image."
        )

    with tempfile.TemporaryDirectory(prefix="mf_pdf_") as tmp:
        tmp_path = Path(tmp)
        in_file = tmp_path / f"{uuid.uuid4().hex}.docx"
        in_file.write_bytes(docx_bytes)

        try:
            proc = subprocess.run(
                [
                    bin_path,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(tmp_path),
                    str(in_file),
                ],
                capture_output=True,
                timeout=timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PdfConvertError(f"soffice conversion timed out after {timeout_sec}s") from exc

        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", "ignore")
            raise PdfConvertError(f"soffice failed (rc={proc.returncode}): {stderr.strip()}")

        out_file = in_file.with_suffix(".pdf")
        if not out_file.exists():
            raise PdfConvertError("soffice succeeded but PDF was not produced")
        return out_file.read_bytes()
