"""PDF ingestion: tables whose rows the PDF breaks apart, a clause that is not on page 1, and scans routed to OCR (all offline)."""
import io
from pathlib import Path

import pymupdf
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app import extract as ex
from app import ocr
from app.extract import extract_from_llm, pdf_pages, pdf_stats, postprocess
from app.schema import ContractData
from tests.fakes import FakeClient
from tests.test_ocr import FakeEngine, clean_env, make_scan, use  # noqa: F401  (clean_env is an autouse fixture there)

ROWS = [("Instalment", "Percent", "Due date", "Stage"), ("Booking", "10%", "14 January 2025", "On signing"),
        ("Foundation", "20%", "15 July 2025", "On foundation"), ("Structure", "70%", "31 March 2026", "On structure")]


def table_pdf(by_column: bool) -> bytes:
    """A ruled payment table. Some exporters draw it column by column; the page then READS as columns, not rows."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 10)
    xs, y0, rh = [50, 160, 230, 360, 520], 700, 22
    cells = [(i, j) for j in range(4) for i in range(4)] if by_column else [(i, j) for i in range(4) for j in range(4)]
    for i, j in cells:
        c.drawString(xs[j] + 4, y0 - i * rh - 15, ROWS[i][j])
    for i in range(5):
        c.line(xs[0], y0 - i * rh, xs[-1], y0 - i * rh)
    for x in xs:
        c.line(x, y0, x, y0 - 4 * rh)
    c.save()
    return buf.getvalue()


def blank_fields():
    nul = {"value": None, "source_page": None, "source_quote": None}
    return {k: dict(nul) for k in ("buyer", "unit_id", "price", "area_sqft", "handover_date", "grace_period_days", "delay_rate",
                                   "delay_basis", "delay_cap", "cancellation_clause")} | {"payment_plan": [], "dated_clauses": []}


def plan_input():
    inp = blank_fields()
    for name, pct, date_, stage in ROWS[1:]:
        inp["payment_plan"].append({"name": name, "percent": float(pct.rstrip("%")), "due_date": None, "trigger": stage, "source_page": 1,
                                    "source_quote": f"{name} {pct} {date_} {stage}"})
    return inp


def run(pdf: bytes, inp: dict) -> ContractData:
    return postprocess(ContractData(**extract_from_llm(pdf, FakeClient(inp)).model_dump()), pdf_pages(pdf), pdf)


# ------------------------------------------------------------------ tables
def test_a_table_drawn_column_by_column_is_read_row_by_row():
    pdf = table_pdf(by_column=True)
    raw = pymupdf.open(stream=pdf, filetype="pdf")[0].get_text()
    assert "Booking 10%" not in " ".join(raw.split())                       # the plain text really is scrambled
    page = pdf_pages(pdf)[0]
    assert ex.TABLE_ROWS_MARK in page
    for name, pct, date_, stage in ROWS[1:]:
        assert f"{name} {pct} {date_} {stage}" in page                      # every row, whole, with its spaces


def test_the_payment_plan_of_a_scrambled_table_is_grounded_not_thrown_away(monkeypatch):
    pdf = table_pdf(by_column=True)
    c = run(pdf, plan_input())
    assert len(c.payment_plan) == 3 and not c.ungrounded_rows and c.payment_plan_percent_sum == 100
    assert all(m.grounding.status == "grounded" and m.source_page == 1 for m in c.payment_plan)
    assert all(m.evidence is not None and m.evidence.page == 1 for m in c.payment_plan)    # and each row can be highlighted on the page


def test_without_the_repair_the_same_plan_is_lost(monkeypatch):
    """Proof the repair matters: with it switched off, every row of the scrambled table is ungrounded and the plan disappears."""
    monkeypatch.setattr(ex, "_table_rows_missing", lambda page, text: [])
    ex._pages.cache_clear()
    try:
        c = run(table_pdf(by_column=True), plan_input())
        assert c.payment_plan == [] and len(c.ungrounded_rows) == 3
    finally:
        ex._pages.cache_clear()


def test_a_table_drawn_row_by_row_is_left_exactly_as_it_was():
    pdf = table_pdf(by_column=False)
    assert ex.TABLE_ROWS_MARK not in pdf_pages(pdf)[0]
    assert run(pdf, plan_input()).payment_plan_percent_sum == 100


@pytest.mark.parametrize("path", sorted(list(Path("samples").glob("*.pdf")) + list(Path("samples/crossdoc").glob("*/*.pdf"))), ids=lambda p: p.name)
def test_every_existing_document_reads_exactly_as_before(path):
    """The repair adds text only when a table's rows are broken. Nothing that already read correctly changes, so no earlier quote can move."""
    data = path.read_bytes()
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        assert pdf_pages(data) == [p.get_text() for p in doc]


# ------------------------------------------------------------------ a clause that is not on page 1
def long_pdf() -> bytes:
    doc = pymupdf.open()
    texts = ["Cover page: the parties to this Agreement for Sale.", "Definitions and interpretation of the terms used here.",
             "Payment terms apply as scheduled in the annexure.",
             "If possession is late the Developer shall pay compensation at 7% per annum of the price paid.",
             "Governing law, jurisdiction and signatures of the parties."]
    for t in texts:
        doc.new_page().insert_text((72, 100), t, fontsize=11)
    return doc.tobytes()


def test_a_clause_on_page_four_is_found_on_page_four_even_when_the_model_says_page_one():
    pdf = long_pdf()
    inp = blank_fields()
    quote = "the Developer shall pay compensation at 7% per annum"
    inp["delay_rate"] = {"value": 7.0, "source_page": 1, "source_quote": quote}                 # the model got the page wrong
    inp["delay_basis"] = {"value": "percent_per_annum", "source_page": 4, "source_quote": "7% per annum"}
    c = run(pdf, inp)
    assert c.delay_rate.source_page == 4                                                           # corrected from the document itself
    assert c.delay_rate.grounding.status == "grounded" and c.delay_rate.value == 7.0
    assert c.delay_rate.evidence.page == 4 and c.delay_rate.evidence.rects                           # and the highlight is on page 4
    assert c.delay_basis.source_page == 4


def test_a_quote_that_is_on_no_page_is_still_refused():
    inp = blank_fields()
    inp["delay_rate"] = {"value": 7.0, "source_page": 4, "source_quote": "interest at 7% per annum compounded monthly"}
    c = run(long_pdf(), inp)
    assert c.delay_rate.value is None and c.delay_rate.grounding.status == "ungrounded"


# ------------------------------------------------------------------ scans
def test_each_page_is_routed_by_what_it_contains():
    text = long_pdf()
    scan = make_scan(text)
    mixed = make_scan(text, only={2})
    rep = ocr.ingest_report
    assert rep(text)["route"] == "text" and rep(text)["text_pages"] == [1, 2, 3, 4, 5] and rep(text)["scan_pages"] == []
    assert rep(scan)["route"] == "ocr" and rep(scan)["scan_pages"] == [1, 2, 3, 4, 5]
    assert rep(mixed)["route"] == "mixed" and rep(mixed)["scan_pages"] == [2] and rep(mixed)["text_pages"] == [1, 3, 4, 5]
    blank = pymupdf.open(); blank.new_page()
    assert rep(blank.tobytes()) == {"pages": 1, "text_pages": [], "scan_pages": [], "blank_pages": [1], "route": "blank"}
    assert pdf_stats(scan)["scanned_suspect"] and not pdf_stats(Path("samples/sample_a.pdf").read_bytes())["scanned_suspect"]   # a real contract has far more text per page
    assert ocr.pages_needing_ocr(mixed) == [2]                                                    # the old function agrees with the report


def test_a_scan_becomes_text_after_ocr_and_is_then_routed_as_text(monkeypatch):
    original = long_pdf()
    use(monkeypatch, FakeEngine("fake", original))
    scan = make_scan(original)
    searchable, report = ocr.make_searchable(scan)
    assert ocr.ingest_report(scan)["route"] == "ocr" and ocr.ingest_report(searchable)["route"] == "text"
    inp = blank_fields()
    inp["delay_rate"] = {"value": 7.0, "source_page": 4, "source_quote": "the Developer shall pay compensation at 7% per annum"}
    c = run(searchable, inp)
    assert c.delay_rate.source_page == 4 and c.delay_rate.value == 7.0                          # a clause deep in a scan still resolves
