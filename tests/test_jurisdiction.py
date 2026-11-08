"""Jurisdiction detection and currency: a Dubai contract that mentions 'RERA' must not become an Indian one."""
from __future__ import annotations

from app.grounding import printed_currency
from app.packs import detect_pack

DUBAI_P1 = ("Seller: Frontline Investment Management Co. (L.L.C.), P.O. Box 2195, Dubai, UAE, registered as a developer "
            "with RERA (No. 1021). Correspondence Address: #807, Dorray Bay Building, Dubai Marina. City: Dubai")
DUBAI_P2 = "TOTAL: AED 1,457,000.00 (One Million Four Hundred Dirhams only.) Unit Price: AED 1,457,000.00"


def test_dubai_contract_that_mentions_rera_is_dubai():
    assert detect_pack([DUBAI_P1, DUBAI_P2])[0] == "ae_dubai"


def test_bare_rera_alone_still_falls_back_to_india():
    assert detect_pack(["The project is registered with RERA under number P51800012345."])[0] == "in_rera"


def test_indian_act_wins_even_if_dubai_is_mentioned():
    pages = ["Under the Real Estate (Regulation and Development) Act, 2016. Buyer currently lives in Dubai."]
    assert detect_pack(pages)[0] == "in_rera"


def test_no_keywords_no_pack():
    assert detect_pack(["A contract with no place names."]) is None


def test_currency_comes_from_the_contract_not_the_pack():
    assert printed_currency([DUBAI_P1, DUBAI_P2], 1457000.0) == "AED"
    assert printed_currency(["Sale price Rs. 24,50,000.00"], 2450000.0) is None      # Indian digit grouping: unknown -> pack fallback
    assert printed_currency(["Total price: INR 2,450,000.00"], 2450000.0) == "INR"
    assert printed_currency(["Total 2,450,000.00 USD payable"], 2450000.0) == "USD"


def test_currency_unclear_or_missing_price_is_none():
    assert printed_currency(["no amounts here"], 1457000.0) is None
    assert printed_currency([DUBAI_P2], None) is None
    assert printed_currency(["AED 1,457,000.00 and INR 1,457,000.00"], 1457000.0) is None   # tie: do not guess


def test_full_pipeline_dubai_rera_text_gives_aed(monkeypatch):
    """End to end through postprocess: pages say Dubai + RERA + AED, so jurisdiction is ae_dubai and currency AED."""
    from app.extract import postprocess
    from app.schema import ContractData
    c = ContractData(**{"buyer": {}, "unit_id": {}, "price": {"value": 1457000.0, "source_page": 2, "source_quote": "TOTAL: AED 1,457,000.00"},
                        "area_sqft": {}, "handover_date": {}, "grace_period_days": {}, "delay_rate": {}, "delay_basis": {},
                        "delay_cap": {}, "cancellation_clause": {}, "payment_plan": [], "dated_clauses": []})
    import pymupdf
    doc = pymupdf.open()
    for t in (DUBAI_P1, DUBAI_P2):
        doc.new_page().insert_text((40, 80), t[:90])
    out = postprocess(c, [DUBAI_P1, DUBAI_P2], doc.tobytes())
    assert out.jurisdiction_detected.value == "ae_dubai" and out.currency == "AED"


def test_printed_currency_beats_pack_currency():
    """Indian-law contract priced in USD: the pack says INR, the contract says USD, the contract wins."""
    import pymupdf
    from app.extract import postprocess
    from app.schema import ContractData
    pages = ["Under the Real Estate (Regulation and Development) Act, 2016.", "Total price: USD 250,000.00 payable in instalments."]
    base = {k: {} for k in ("buyer", "unit_id", "area_sqft", "handover_date", "grace_period_days", "delay_rate", "delay_basis",
                            "delay_cap", "cancellation_clause")}
    c = ContractData(**base, price={"value": 250000.0, "source_page": 2, "source_quote": "Total price: USD 250,000.00"},
                     payment_plan=[], dated_clauses=[])
    doc = pymupdf.open()
    for t in pages:
        doc.new_page().insert_text((40, 80), t[:80])
    out = postprocess(c, pages, doc.tobytes())
    assert out.jurisdiction_detected.value == "in_rera" and out.currency == "USD"
