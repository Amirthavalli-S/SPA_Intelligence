"""Generate the "Green Valley" demo story: one coherent set of SYNTHETIC documents a salesperson can walk a client through.

  * AGR-1105  SPA (14 Jan 2025) + Addendum 1 (10 Mar 2026: price only) + Extension Letter (18 Jul 2026: possession only)
  * AGR-1108  one SPA (2 Feb 2025) drafted on a discontinued template, so the company rulebook has things to flag
  * project documents: RERA filing and brochure; plus a CRM export with a deliberately stale possession date

Every document says SYNTHETIC SAMPLE on every page. All values live in the constants below; the PDFs, the CRM export, the oracle
facts, the golden labels and the agreement defaults are all written from them, so nothing can drift.

Run:  python scripts/generate_pgv.py
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.extract import locate_quote, pdf_pages  # noqa: E402

SAMPLES, XD, GOLD = ROOT / "samples", ROOT / "samples" / "crossdoc" / "set_4_pgv", ROOT / "eval" / "golden"
PROJECT = "Prestige Green Valley, Chennai"            # a fictional project name; change here if it is too close to a real brand
RERA = "TN/29/Building/0234/2025"
SELLER = "Green Valley Developers Private Limited"
FOOT = "SYNTHETIC SAMPLE - NOT A REAL CONTRACT"
RERA_COMMITTED = "2028-12-31"

PLAN_1105 = [("Booking", 10, "2025-01-14", "On signing of this Agreement"), ("Foundation", 20, "2025-07-15", "On completion of the foundation"),
             ("Structure", 25, "2026-03-31", "On completion of the structure"), ("Finishing", 25, "2027-06-30", "On completion of internal finishing"),
             ("Possession", 20, "2028-12-31", "On offer of possession")]
PLAN_1108 = [("Booking", 10, "2025-02-02", "On signing of this Agreement"), ("Foundation", 20, "2025-08-15", "On completion of the foundation"),
             ("Structure", 20, "2026-04-30", "On completion of the structure"), ("Finishing", 20, "2027-07-31", "On completion of internal finishing"),
             ("Possession", 30, "2028-12-31", "On offer of possession")]


def long_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


DOCS = {
    "pgv_agr1105_spa": dict(file="pgv_agr1105_spa.pdf", agreement="AGR-1105", doc_type="SPA", signed="2025-01-14", buyer="Ravi Kumar S",
                            unit="A-1105", area=1150, price="Rs. 1,00,00,000", price_words="Rupees One Crore only", price_value=10_000_000,
                            handover=RERA_COMMITTED, plan=PLAN_1105, rate=10, rate_text="Rs. 10 per sq ft per month", grace=0,
                            refund=True, force_majeure=True, postpone=None, template="SPA TEMPLATE v2.1"),
    "pgv_agr1108_spa": dict(file="pgv_agr1108_spa.pdf", agreement="AGR-1108", doc_type="SPA", signed="2025-02-02", buyer="Fathima Noor A",
                            unit="A-1108", area=980, price="Rs. 85,00,000", price_words="Rupees Eighty-Five Lakh only", price_value=8_500_000,
                            handover=RERA_COMMITTED, plan=PLAN_1108, rate=5, rate_text="Rs. 5 per sq ft per month", grace=None,
                            refund=False, force_majeure=True, postpone=24, template="SPA TEMPLATE v1.0 (DISCONTINUED IN 2024)"),
}
ADDENDUM = dict(file="pgv_agr1105_addendum1.pdf", doc_id="pgv_agr1105_addendum1", doc_type="Addendum", signed="2026-03-10",
                price="Rs. 95,00,000", price_words="Rupees Ninety-Five Lakh only", price_value=9_500_000)
EXTENSION = dict(file="pgv_agr1105_extension.pdf", doc_id="pgv_agr1105_extension", doc_type="Extension Letter", signed="2026-07-18",
                 handover="2029-06-30")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=17, spaceAfter=8)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=3)
P = ParagraphStyle("p", parent=ss["BodyText"], fontSize=10.2, leading=14.2, spaceAfter=5)


def build(path: Path, foot: str, blocks: list) -> None:
    def deco(c, d):
        c.saveState()
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(colors.HexColor("#8a2d1c"))
        c.drawString(20 * mm, 11 * mm, f"{FOOT}  |  {foot}  |  Page {d.page}")
        c.restoreState()
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=20 * mm,
                            title=foot, author="Synthetic demo data")
    out = []
    for b in blocks:
        kind = b[0]
        if kind == "h1": out.append(Paragraph(b[1], H1))
        elif kind == "h2": out.append(Paragraph(b[1], H2))
        elif kind == "p": out.append(Paragraph(b[1], P))
        elif kind == "sp": out.append(Spacer(1, b[1] * mm))
        elif kind == "pb": out.append(PageBreak())
        elif kind == "table":
            t = Table(b[1], colWidths=b[2], repeatRows=1)
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9e2d0")), ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                                   ("FONTSIZE", (0, 0), (-1, -1), 9.2), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            out.append(t)
    doc.build(out, onFirstPage=deco, onLaterPages=deco)


def spa_blocks(d: dict) -> list:
    plan_rows = [["Instalment", "Percent", "Due date", "Stage"]] + [[n, f"{p:g}%", long_date(dt), tr] for n, p, dt, tr in d["plan"]]
    b = [("h1", "AGREEMENT FOR SALE"), ("p", f"Project: {PROJECT}"), ("p", f"RERA Registration No. {RERA}"),
         ("p", f"This Agreement is made on {long_date(d['signed'])} between {SELLER} (the Developer) and the Purchaser named below."),
         ("h2", "1. Parties and Unit"), ("p", f"Purchaser: {d['buyer']}"), ("p", f"Unit: {d['unit']}, Tower A"),
         ("p", f"Super built-up area: {d['area']:,} sq ft"), ("pb",),
         ("h2", "2. Sale consideration"), ("p", f"The total sale consideration for the Unit is {d['price']} ({d['price_words']})."),
         ("h2", "3. Payment plan"), ("table", plan_rows, [38 * mm, 22 * mm, 40 * mm, 70 * mm]), ("sp", 4),
         ("h2", "4. Possession"), ("p", f"The Developer shall hand over possession of the Unit on or before {long_date(d['handover'])}."), ("pb",),
         ("h2", "5. Delay in possession")]
    if d["postpone"]:
        b += [("p", f"The Developer may postpone the date of possession by up to {d['postpone']} months without any liability. "
                    f"If possession is not handed over after that period, the Developer shall pay compensation of {d['rate_text']} "
                    f"of the Unit area for each month of delay.")]
    else:
        b += [("p", f"If possession is not handed over by the date in Clause 4, the Developer shall pay compensation of {d['rate_text']} "
                    f"of the Unit area for each month of delay."), ("p", f"Grace period: {d['grace']} days.")]
    b += [("h2", "6. Termination and refund")]
    if d["refund"]:
        b += [("p", "If the Developer fails to complete and hand over the Unit for any reason attributable to the Developer, the Purchaser may "
                    "withdraw and the Developer shall refund the full amount received with interest at 8% p.a.")]
    else:
        b += [("p", "The Purchaser may not withdraw from this Agreement except as expressly agreed in writing by the Developer.")]
    b += [("h2", "7. Force Majeure"), ("p", "Neither party is liable for delay caused by events beyond its reasonable control, provided written "
                                              "notice is given within 15 days of the event."),
          ("h2", "8. Governing law"), ("p", "This Agreement is governed by the laws of India."), ("sp", 10),
          ("p", "Signed for the Developer: ______________________    Signed by the Purchaser: ______________________"),
          ("p", f"Document type: {d['template']}")]
    return b


def make_pdfs() -> dict[str, Path]:
    SAMPLES.mkdir(exist_ok=True)
    out = {}
    for key, d in DOCS.items():
        build(SAMPLES / d["file"], f"{d['agreement']} {d['doc_type']}", spa_blocks(d)); out[key] = SAMPLES / d["file"]
    a = ADDENDUM
    build(SAMPLES / a["file"], "AGR-1105 Addendum 1", [
        ("h1", "ADDENDUM NO. 1"), ("p", f"to the Agreement for Sale dated {long_date('2025-01-14')}"), ("p", f"Project: {PROJECT}"),
        ("p", f"This Addendum is made on {long_date(a['signed'])} between {SELLER} and {DOCS['pgv_agr1105_spa']['buyer']}, Unit A-1105, Tower A."),
        ("h2", "1. Revised sale consideration"),
        ("p", f"The sale consideration stated in Clause 2 of the Agreement is revised to {a['price']} ({a['price_words']})."),
        ("h2", "2. Other terms"), ("p", "All other terms and conditions of the Agreement remain unchanged."), ("sp", 10),
        ("p", "Signed for the Developer: ______________________    Signed by the Purchaser: ______________________")])
    out[a["doc_id"]] = SAMPLES / a["file"]
    e = EXTENSION
    build(SAMPLES / e["file"], "AGR-1105 Extension Letter", [
        ("h1", "EXTENSION LETTER"), ("p", f"Date: {long_date(e['signed'])}"), ("p", f"Project: {PROJECT}"),
        ("p", f"To: {DOCS['pgv_agr1105_spa']['buyer']}, Unit A-1105, Tower A"),
        ("p", f"Further to the Agreement for Sale dated {long_date('2025-01-14')}, the date of possession in Clause 4 is revised to "
              f"{long_date(e['handover'])}."), ("p", "All other terms and conditions of the Agreement remain unchanged."), ("sp", 10),
        ("p", "Signed for the Developer: ______________________")])
    out[e["doc_id"]] = SAMPLES / e["file"]
    # project-level documents (crossdoc set 4)
    XD.mkdir(parents=True, exist_ok=True)
    build(XD / "filing.pdf", "RERA project filing", [
        ("h1", "RERA PROJECT REGISTRATION (EXTRACT)"), ("p", f"Project: {PROJECT}"), ("p", f"Registration No. {RERA}"),
        ("p", f"Proposed date of completion: {long_date(RERA_COMMITTED)}"), ("p", "Registered with the Tamil Nadu Real Estate Regulatory Authority.")])
    build(XD / "brochure.pdf", "Project brochure", [
        ("h1", PROJECT), ("p", "Homes with a garden view, close to the city."), ("p", "Prices starting from Rs. 82,00,000 (indicative)."),
        ("p", f"Possession: {long_date(RERA_COMMITTED)}"), ("p", f"RERA Registration No. {RERA}")])
    shutil.copy(SAMPLES / DOCS["pgv_agr1105_spa"]["file"], XD / "spa.pdf")
    return out


# ------------------------------------------------------------------ labels, CRM, facts, manifest, agreement defaults
def S(pages, value, quote):
    if quote is None:
        return {"value": value, "page": None, "quote": None}
    pg = locate_quote(pages, quote)
    assert pg, f"quote not found in the PDF: {quote!r}"
    return {"value": value, "page": pg, "quote": quote}


def spa_labels(d: dict):
    def f(pages):
        L = {"buyer": S(pages, d["buyer"], d["buyer"]), "unit_id": S(pages, d["unit"], f"{d['unit']}, Tower A"),
             "price": S(pages, d["price_value"], d["price"]), "area_sqft": S(pages, float(d["area"]), f"{d['area']:,} sq ft"),
             "handover_date": S(pages, d["handover"], long_date(d["handover"])),
             "delay_rate": S(pages, float(d["rate"]), d["rate_text"]), "delay_basis": S(pages, "fixed_per_sqft_per_month", d["rate_text"]),
             "delay_cap": {"value": None, "page": None, "quote": None},
             "payment_plan": [], "dated_clauses": []}
        L["grace_period_days"] = S(pages, d["grace"], f"Grace period: {d['grace']} days") if d["grace"] is not None else {"value": None, "page": None, "quote": None}
        L["cancellation_clause"] = (S(pages, "present", "the Developer shall refund the full amount received with interest at 8% p.a.")
                                    if d["refund"] else {"value": None, "page": None, "quote": None})
        for n, p, dt, tr in d["plan"]:
            q = f"{n} {p:g}% {long_date(dt)} {tr}"
            L["payment_plan"].append({"name": n, "percent": float(p), "due_date": dt, "trigger": tr, "page": locate_quote(pages, q), "quote": q})
        if d["postpone"]:
            L["dated_clauses"].append({"kind": "other", "description": "Postponement allowed before compensation applies", "amount": d["postpone"],
                                       "unit": "months", "anchor": "handover_date", "page": locate_quote(pages, f"up to {d['postpone']} months"),
                                       "quote": f"up to {d['postpone']} months"})
        return L
    return f


def write_golden(doc_id: str, pdf: Path, fn) -> None:
    pages = pdf_pages(pdf.read_bytes())
    nul = {"value": None, "page": None, "quote": None}
    lab = {"doc_id": doc_id, "kind": "synthetic", "synthetic": True, "currency": "INR",
           "note": "Synthetic Green Valley demo document. Labels are known by construction.",
           "buyer": nul, "unit_id": nul, "price": nul, "area_sqft": nul, "handover_date": nul, "grace_period_days": nul, "delay_rate": nul,
           "delay_basis": nul, "delay_cap": nul, "cancellation_clause": nul, "payment_plan": [], "dated_clauses": []}
    lab.update(fn(pages))
    d = GOLD / doc_id
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(pdf, d / "doc.pdf")
    (d / "labels.json").write_text(json.dumps(lab, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    pdfs = make_pdfs()
    for key, d in DOCS.items():
        write_golden(key, pdfs[key], spa_labels(d))
    a, e, s = ADDENDUM, EXTENSION, DOCS["pgv_agr1105_spa"]
    write_golden(a["doc_id"], pdfs[a["doc_id"]], lambda pg: {"buyer": S(pg, s["buyer"], s["buyer"]), "unit_id": S(pg, s["unit"], f"{s['unit']}, Tower A"),
                                                              "price": S(pg, a["price_value"], a["price"])})
    write_golden(e["doc_id"], pdfs[e["doc_id"]], lambda pg: {"buyer": S(pg, s["buyer"], s["buyer"]), "unit_id": S(pg, s["unit"], f"{s['unit']}, Tower A"),
                                                              "handover_date": S(pg, e["handover"], long_date(e["handover"]))})
    # agreement defaults for the sample documents
    defaults = {DOCS[k]["file"]: {"agreement_id": DOCS[k]["agreement"], "doc_type": DOCS[k]["doc_type"], "date_signed": DOCS[k]["signed"]} for k in DOCS}
    defaults[a["file"]] = {"agreement_id": "AGR-1105", "doc_type": a["doc_type"], "date_signed": a["signed"]}
    defaults[e["file"]] = {"agreement_id": "AGR-1105", "doc_type": e["doc_type"], "date_signed": e["signed"]}
    (SAMPLES / "agreements.json").write_text(json.dumps(defaults, indent=2) + "\n", encoding="utf-8")
    # CRM export: one row per agreement. AGR-1105's possession date is deliberately STALE (a third, different date).
    with open(XD / "crm.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Unit No", "Customer", "Agreed Price", "Area", "Possession Date", "Plan %", "Delay Rate", "RERA No"])
        w.writerow(["A-1105", "Ravi Kumar S", 9500000, 1150.0, "31-03-2029", "10/20/25/25/20", 10.0, RERA])
        w.writerow(["A-1108", "Fathima Noor A", 8500000, 980.0, "31-12-2028", "10/20/20/20/30", 5.0, RERA])
    # oracle facts for the two project-level PDFs (they state no unit, and the brochure's "starting from" price is not this unit's price)
    def fact(doc, **kv):
        return {"doc": doc, "quotes": {k: v[1] for k, v in kv.items()}, "values": {k: v[0] for k, v in kv.items()}}
    facts = {"brochure": fact("brochure.pdf", handover_date=(RERA_COMMITTED, f"Possession: {long_date(RERA_COMMITTED)}"),
                              registration_number=(RERA, f"RERA Registration No. {RERA}")),
             "filing": fact("filing.pdf", handover_date=(RERA_COMMITTED, f"Proposed date of completion: {long_date(RERA_COMMITTED)}"),
                            registration_number=(RERA, f"Registration No. {RERA}"))}
    (XD / "facts.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    manifest = {"set_id": "set_4_pgv", "unit_key": "A-1105", "spa": "spa.pdf", "currency": "INR", "agreement_id": "AGR-1105",
                "crm_area_unit": "sqft",
                "documents": [{"type": "spa", "file": "spa.pdf"}, {"type": "brochure", "file": "brochure.pdf", "scope": "project"},
                              {"type": "regulator_filing", "file": "filing.pdf", "scope": "project"}, {"type": "crm_export", "file": "crm.csv"}],
                "planted": [{"attribute": "handover_date", "docs": ["spa", "brochure", "regulator_filing", "crm_export"]}]}
    (XD / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("wrote", len(pdfs), "PDFs, 4 golden folders, set_4_pgv, agreements.json")


if __name__ == "__main__":
    main()
