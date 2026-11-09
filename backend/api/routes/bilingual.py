"""Arabic vs English version of one contract: clause-by-clause figure comparison (no model call, no stored change)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Query, UploadFile

from app import bilingual_check, config
from app.extract import pdf_pages
from backend.api import deps
from backend.api.deps import ApiError

router = APIRouter(tags=["bilingual"])
SAMPLE_DIR = config.ROOT / "samples" / "bilingual"


def _pages(data: bytes) -> list[str]:
    if not data.startswith(b"%PDF-"):
        raise ApiError(415, "not_a_pdf", "Only PDF files are accepted.")
    try:
        return pdf_pages(data)
    except Exception:  # noqa: BLE001
        raise ApiError(415, "not_a_pdf", "The file could not be read as a PDF.") from None


@router.post("/contracts/{contract_id}/bilingual-check")
async def bilingual_check_route(contract_id: str, sample: Optional[str] = Query(None, pattern="^[a-z0-9_]{1,30}$"),
                                arabic: Optional[UploadFile] = File(None)):
    """English = this contract's PDF; Arabic = the uploaded PDF. `sample=pair_1` compares the bundled synthetic pair instead."""
    deps.get_source(contract_id)
    if sample:
        d = SAMPLE_DIR / sample
        if not (d / "en.pdf").exists():
            raise ApiError(404, "not_found", "No such sample pair.")
        en, ar = _pages((d / "en.pdf").read_bytes()), _pages((d / "ar.pdf").read_bytes())
    else:
        if arabic is None:
            raise ApiError(422, "arabic_missing", "Upload the Arabic version of this contract as a PDF.")
        data = await arabic.read(config.MAX_UPLOAD_BYTES + 1)
        if len(data) > config.MAX_UPLOAD_BYTES:
            raise ApiError(413, "file_too_large", "File is too large.")
        en, ar = _pages(deps.get_source(contract_id).path.read_bytes()), _pages(data)
    if not any(p.strip() for p in ar):
        raise ApiError(422, "no_text", "The Arabic PDF has no readable text (a scan needs OCR first).")
    out = bilingual_check.check(en, ar)
    out["disclaimer"] = "Decision support, not legal advice. Compares figures only; the Arabic text needs review by a native speaker."
    return out
