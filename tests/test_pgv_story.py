"""The Green Valley demo story: the documents, the rulebook verdicts and the penalty figure are what the story says they are."""
import json
from pathlib import Path

import pytest

from app import playbook as pb
from app.extract import extract_from_llm, locate_quote, pdf_pages, postprocess
from app.penalty import penalty_for_contract
from app.schema import ContractData
from eval.labels import labels_to_tool_input
from tests.fakes import FakeClient

GOLD = Path("eval/golden")
DOCS = ["pgv_agr1105_spa", "pgv_agr1105_addendum1", "pgv_agr1105_extension", "pgv_agr1108_spa"]


def load(doc_id):
    d = GOLD / doc_id
    return (d / "doc.pdf").read_bytes(), json.loads((d / "labels.json").read_text())


def contract(doc_id) -> ContractData:
    b, labels = load(doc_id)
    return postprocess(ContractData(**extract_from_llm(b, FakeClient(labels_to_tool_input(labels))).model_dump()), pdf_pages(b), b)


def verdicts(doc_id):
    b, _ = load(doc_id)
    c = contract(doc_id)
    res = pb.evaluate(c, b, "in_rera", None)
    return {r["rule_id"]: r for r in res["results"] if r["rule_id"].startswith("gv_")}


@pytest.mark.parametrize("doc_id", DOCS)
def test_every_label_quote_is_on_the_page_the_label_says(doc_id):
    b, labels = load(doc_id)
    pages = pdf_pages(b)
    for k, v in labels.items():
        if isinstance(v, dict) and v.get("quote"):
            assert locate_quote(pages, v["quote"]) == v["page"], (doc_id, k)
    for row in labels["payment_plan"]:
        assert locate_quote(pages, row["quote"]) == row["page"]


@pytest.mark.parametrize("doc_id", DOCS)
def test_every_labelled_value_grounds_in_its_own_pdf_nothing_is_withheld(doc_id):
    """Indian grouping (Rs. 1,00,00,000), a monthly rate and a nil grace period all pass the grounding checks."""
    c = contract(doc_id)
    assert not [w for w in c.warnings if "ungrounded" in w], c.warnings
    assert not c.ungrounded_rows


def test_the_spa_says_what_the_story_says():
    c = contract("pgv_agr1105_spa")
    assert c.price.value == 10_000_000 and c.area_sqft.value == 1150 and c.handover_date.value.isoformat() == "2028-12-31"
    assert c.delay_rate.value == 10 and c.delay_basis.value == "fixed_per_sqft_per_month" and c.grace_period_days.value == 0
    assert c.cancellation_clause.value and c.payment_plan_percent_sum == 100 and c.currency == "INR"
    assert c.jurisdiction_detected.value == "in_rera"


def test_each_amendment_states_only_what_it_changes():
    a, e = contract("pgv_agr1105_addendum1"), contract("pgv_agr1105_extension")
    assert a.price.value == 9_500_000 and a.handover_date.value is None and not a.payment_plan and a.delay_rate.value is None
    assert e.handover_date.value.isoformat() == "2029-06-30" and e.price.value is None and not e.payment_plan


def test_the_demo_penalty_is_hand_calculable():
    """1,150 sq ft x Rs 10 a month x 12 = 138,000 a year; for 90 days: 138,000 x 90 / 365."""
    r = penalty_for_contract(contract("pgv_agr1105_spa"), 90)
    assert r["penalty"] == 34027.4 and r["grace_days"] == 0 and r["chargeable_days"] == 90


# ------------------------------------------------------------------ the company rulebook
def test_agr_1105_passes_every_green_valley_rule():
    v = verdicts("pgv_agr1105_spa")
    assert set(v) == {"gv_postponement_max", "gv_min_rate", "gv_refund_required", "gv_force_majeure_required", "gv_rera_matches"}
    assert {k: r["status"] for k, r in v.items()} == {k: "pass" for k in v}, {k: r["reason"] for k, r in v.items()}


def test_agr_1108_breaks_exactly_the_three_planted_rules():
    v = verdicts("pgv_agr1108_spa")
    assert {k: r["status"] for k, r in v.items()} == {"gv_postponement_max": "fail", "gv_min_rate": "fail", "gv_refund_required": "fail",
                                                      "gv_force_majeure_required": "pass", "gv_rera_matches": "pass"}
    assert "24 months" in v["gv_postponement_max"]["reason"] and "12 months" in v["gv_postponement_max"]["reason"]
    assert v["gv_min_rate"]["reason"].startswith("Compensation is 5 per sq ft per month, below the minimum of 10")
    assert "No clause committing the developer to refund" in v["gv_refund_required"]["reason"]
    assert v["gv_postponement_max"]["evidence"]["page"] == 3                       # points at the clause, not just the document


def test_the_rulebook_rules_are_marked_unreviewed_by_a_lawyer():
    for r in verdicts("pgv_agr1108_spa").values():
        assert r["reviewed_by_lawyer"] is False


def test_the_green_valley_rules_apply_only_to_green_valley_spas():
    for doc in ("pgv_agr1105_addendum1", "pgv_agr1105_extension"):          # amendments are not SPAs
        assert verdicts(doc) == {}
    b = Path("samples/sample_a.pdf").read_bytes()                            # a Dubai contract from another company
    from tests.fakes import oracle_input
    c = postprocess(ContractData(**extract_from_llm(b, FakeClient(oracle_input(Path("samples/sample_a.pdf")))).model_dump()), pdf_pages(b), b)
    assert not [r for r in pb.evaluate(c, b, "ae_dubai", None)["results"] if r["rule_id"].startswith("gv_")]


def test_a_rate_that_is_too_low_per_year_is_compared_as_a_monthly_figure():
    c = contract("pgv_agr1105_spa")
    c.delay_basis.value, c.delay_rate.value = "fixed_per_sqft_per_year", 96.0      # 96 a year = 8 a month: below 10
    b, _ = load("pgv_agr1105_spa")
    res = {r["rule_id"]: r for r in pb.evaluate(c, b, "in_rera", None)["results"]}
    assert res["gv_min_rate"]["status"] == "fail" and "8 per sq ft per month" in res["gv_min_rate"]["reason"]
    c.delay_rate.value = 144.0                                                       # 12 a month: fine
    assert {r["rule_id"]: r for r in pb.evaluate(c, b, "in_rera", None)["results"]}["gv_min_rate"]["status"] == "pass"


def test_a_wrong_rera_number_and_a_low_refund_interest_are_caught():
    b, _ = load("pgv_agr1105_spa")
    c = contract("pgv_agr1105_spa")
    pages = pdf_pages(b)
    bad = [" ".join(p.split()).replace("TN/29/Building/0234/2025", "TN/29/Building/9999/2025").replace("interest at 8% p.a.", "interest at 5% p.a.") for p in pages]
    res = {r["rule_id"]: r for r in pb.run_deterministic(c, bad, b, pb.load_playbook(), "in_rera", []) if r["rule_id"].startswith("gv_")}
    assert res["gv_rera_matches"]["status"] == "fail" and "TN/29/Building/9999/2025" in res["gv_rera_matches"]["reason"]
    assert res["gv_refund_required"]["status"] == "fail" and "5%" in res["gv_refund_required"]["reason"]
