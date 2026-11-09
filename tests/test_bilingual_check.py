"""Arabic vs English version of one contract: planted mismatch found, matching clauses not flagged, visual-order Arabic handled."""
import json
import re
from pathlib import Path

from app import bilingual_check as bc
from app.extract import pdf_pages

D = Path(__file__).resolve().parent.parent / "samples" / "bilingual" / "pair_1"


def pages(name):
    return pdf_pages((D / name).read_bytes())


def test_planted_mismatch_is_found_and_nothing_else_is_flagged():
    r = bc.check(pages("en.pdf"), pages("ar.pdf"))
    planted = json.loads((D / "manifest.json").read_text())["planted"]
    bad = [p for p in r["pairs"] if p["status"] == "mismatch"]
    assert [p["clause_id"] for p in bad] == [x["clause_id"] for x in planted] == ["4"]
    assert "30" in bad[0]["differences"][0] and "15" in bad[0]["differences"][0]
    assert r["summary"] == {"match": 4, "mismatch": 1, "unaligned": 0, "total": 5} and r["paired_by_number"] == 5
    assert r["model_calls"] == 0


def test_pdf_arabic_is_visual_order_and_is_normalised():
    ar = pages("ar.pdf")
    assert bc.is_visual(ar[0])                                  # shaped letters in the PDF text
    assert "2028" in bc.segment(ar)[1].text and "1200000" in "".join(bc.segment(ar)[0].text.replace(",", ""))


def test_digit_runs_stored_reversed_are_turned_back():
    en, ar = pages("en.pdf"), pages("ar.pdf")
    rev = [re.sub(r"\d+(?:[.,]\d+)*", lambda m: m.group(0)[::-1], ar[0])]        # an extractor that reverses numbers: "2028" -> "8202"
    r = bc.check(en, rev)
    assert [p["clause_id"] for p in r["pairs"] if p["status"] == "mismatch"] == ["4"] and r["summary"]["match"] == 4


def test_arabic_indic_digits_and_number_formats_are_equal():
    assert bc.figures(bc.normalize("٣٠ يوماً و ١٠٪")) == bc.figures("30 days and 10%")
    assert bc.figures("AED 1,200,000") == bc.figures("1200000 درهم")


def test_a_changed_figure_in_every_kind_is_caught():
    en = ["1. Price AED 1,200,000.\n2. Pay 10% on signing.\n3. Handover 31 March 2028."]
    for ar_text in ("1. السعر 1,250,000 درهم.\n2. الدفع 10% عند التوقيع.\n3. التسليم 31 مارس 2028.",
                    "1. السعر 1,200,000 درهم.\n2. الدفع 15% عند التوقيع.\n3. التسليم 31 مارس 2028.",
                    "1. السعر 1,200,000 درهم.\n2. الدفع 10% عند التوقيع.\n3. التسليم 31 مارس 2029."):
        r = bc.check(en, [ar_text])
        assert r["summary"]["mismatch"] == 1 and r["summary"]["match"] == 2


def test_clause_with_no_partner_is_unaligned_not_matched():
    r = bc.check(["1. Price AED 100.\n2. Cancel in 30 days."], ["1. السعر 100 درهم."])
    assert {p["clause_id"]: p["status"] for p in r["pairs"]} == {"1": "match", "2": "unaligned"}


def test_pairing_falls_back_to_shared_figures_and_says_so():
    r = bc.check(["1. Price AED 100 and 5% a year."], ["7. السعر 100 درهم و 5% سنوياً."])
    assert r["pairs"][0]["aligned_by"] == "figures" and r["pairs"][0]["status"] == "match"


def test_model_judge_only_sees_pairs_whose_figures_agree():
    seen = []

    def judge(en, ar):
        seen.append(en)
        return {"same": False, "difference": "Arabic says 'may', English says 'shall'"}
    r = bc.check(pages("en.pdf"), pages("ar.pdf"), judge)
    assert len(seen) == 4 == r["model_calls"]                    # the figure mismatch (clause 4) is not sent to the model
    assert r["summary"]["mismatch"] == 5 and any("Wording" in d for p in r["pairs"] for d in p["differences"])
