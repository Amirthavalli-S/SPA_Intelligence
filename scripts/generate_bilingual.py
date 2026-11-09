"""Generate a synthetic English + Arabic version of one contract with ONE planted mismatch (cancellation: 30 days vs 15 days).

Writes samples/bilingual/pair_1/{en.pdf, ar.pdf, manifest.json}. SYNTHETIC; the Arabic needs native review.
Run:  python scripts/generate_bilingual.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "samples" / "bilingual" / "pair_1"
FONTS = "/usr/share/fonts/truetype/dejavu"

EN = [
    "The purchase price of the Unit is AED 1,200,000.",
    "The Seller shall hand over the Unit by 31 March 2028.",
    "The Buyer shall pay 10% of the price on signing.",
    "The Buyer may cancel this agreement within 30 days of signing and receive a full refund.",
    "The Seller shall pay delay compensation of 5% per annum of the amount paid.",
]
AR = [
    "سعر شراء الوحدة هو 1,200,000 درهم إماراتي.",
    "يلتزم البائع بتسليم الوحدة بتاريخ 31 مارس 2028.",
    "يدفع المشتري 10% من السعر عند التوقيع.",
    "يجوز للمشتري إلغاء هذه الاتفاقية خلال 15 يوماً من التوقيع واسترداد المبلغ كاملاً.",
    "يدفع البائع تعويضاً عن التأخير بنسبة 5% سنوياً من المبلغ المدفوع.",
]
PLANTED = [{"clause_id": "4", "attribute": "cancellation_period", "english": "30 days", "arabic": "15 days"}]


def build(path: Path, title: str, clauses: list[str], rtl: bool) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    arch = pymupdf.Archive(FONTS)
    d = "rtl" if rtl else "ltr"
    items = "".join(f"<p dir='{d}'>{i}. {c}</p>" for i, c in enumerate(clauses, 1))
    css = "@font-face {font-family: dj; src: url(DejaVuSans.ttf);} * {font-family: dj; font-size: 12pt;}"
    page.insert_htmlbox(pymupdf.Rect(50, 50, 545, 790), f"<h3 dir='{d}'>{title}</h3>{items}", css=css, archive=arch)
    doc.set_metadata({"title": title})
    doc.save(str(path), deflate=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    build(OUT / "en.pdf", "Sale Agreement (English)", EN, False)
    build(OUT / "ar.pdf", "Sale Agreement (Arabic)", AR, True)
    (OUT / "manifest.json").write_text(json.dumps({"planted": PLANTED, "note": "SYNTHETIC. Arabic needs native review."}, indent=2, ensure_ascii=False))
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
