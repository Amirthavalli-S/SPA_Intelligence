"""The Green Valley cross-document story: three different possession dates, and only because the amendments are reconciled first."""
import json
from datetime import date
from pathlib import Path

from app import crossdoc as cd
from app.crossdoc import analyze, load_set, score_planted
from app.reconcile import Doc, fields_from_contract, overlay_current, reconcile
from tests.test_crossdoc import facts_oracle
from tests.test_pgv_story import contract

SET = Path("samples/crossdoc/set_4_pgv")
SIGNED = {"pgv_agr1105_spa": ("SPA", date(2025, 1, 14)), "pgv_agr1105_addendum1": ("Addendum", date(2026, 3, 10)),
          "pgv_agr1105_extension": ("Extension Letter", date(2026, 7, 18))}


def effective():
    contracts = {k: contract(k) for k in SIGNED}
    docs = [Doc(k, k, t, d, fields_from_contract(contracts[k])) for k, (t, d) in SIGNED.items()]
    res = reconcile("AGR-1105", docs)
    return res, *overlay_current("pgv_agr1105_spa", res, contracts)


def test_reconciling_the_story_gives_the_effective_terms_the_demo_promises():
    res, eff, changed = effective()
    c = res["current"]
    assert c["price"] == 9_500_000 and c["possession_date"] == "2029-06-30" and c["payment_plan_version"] == 1
    assert c["penalty_rate"] == {"rate": 10.0, "basis": "fixed_per_sqft_per_month"}
    assert [t["doc_type"] for t in res["timeline"]] == ["SPA", "Addendum", "Extension Letter"]
    assert changed == {"price", "handover_date"}
    assert eff.price.value == 9_500_000 and eff.handover_date.value.isoformat() == "2029-06-30"
    assert eff.price.source_quote.startswith("[Addendum signed 2026-03-10] ")
    assert eff.handover_date.source_quote.startswith("[Extension Letter signed 2026-07-18] ")
    assert eff.delay_rate.source_quote == "Rs. 10 per sq ft per month" and len(eff.payment_plan) == 5      # untouched terms stay as signed


def run(eff, overlaid):
    return analyze(load_set(SET), eff, facts_oracle(SET), overlaid)


def test_three_different_possession_dates_and_nothing_else_disagrees():
    _, eff, changed = effective()
    res = run(eff, changed)
    assert [c["attribute"] for c in res["conflicts"]] == ["handover_date"]
    vals = {(f["doc_type"], f["raw"] if isinstance(f["raw"], str) else str(f["raw"])) for f in res["conflicts"][0]["values"]}
    assert {t for t, _ in vals} == {"spa", "brochure", "regulator_filing", "crm_export"}
    assert sorted({v for _, v in vals}) == ["2028-12-31", "2029-03-31", "2029-06-30"]                 # RERA/brochure, CRM, the amended contract
    sc = score_planted(res["conflicts"], json.loads((SET / "manifest.json").read_text())["planted"])
    assert sc["precision"] == 1.0 and sc["recall"] == 1.0
    agreed = {a["attribute"] for a in res["agreements"]}
    assert {"price", "area_sqft", "payment_plan", "delay_rate"} <= agreed                              # the CRM and the amended SPA agree on these


def test_project_documents_speak_for_the_whole_project_and_are_not_dropped_for_having_no_unit():
    _, eff, changed = effective()
    docs = {d["type"]: d for d in run(eff, changed)["documents"]}
    assert docs["brochure"]["match"] == "project" and docs["regulator_filing"]["match"] == "project"
    assert "applies to every unit" in docs["brochure"]["note"]
    assert docs["crm_export"]["match"] != "unmatched" and docs["spa"]["match"] != "pending"


def test_evidence_never_points_at_the_original_spa_for_a_value_an_amendment_changed():
    _, eff, changed = effective()
    facts = cd.facts_from_contract(eff, "spa", changed)
    by = {f.attribute: f for f in facts}
    assert by["price"].field is None and by["handover_date"].field is None          # these came from the amendments
    assert by["area_sqft"].field == "area_sqft" and by["delay_rate"].field == "delay_rate"


def test_without_the_amendments_the_picture_is_wrong_in_the_other_direction():
    """The original SPA alone still says 1 crore and 31 Dec 2028, so it would 'match' the filing and brochure and clash with the CRM on price."""
    res = analyze(load_set(SET), contract("pgv_agr1105_spa"), facts_oracle(SET))
    attrs = {c["attribute"]: c for c in res["conflicts"]}
    assert set(attrs) == {"price", "handover_date"}
    assert {f["doc_type"] for f in attrs["price"]["values"]} == {"spa", "crm_export"}
    handover = {tuple(sorted({f["doc_type"] for f in v})) for v in [[x for x in attrs["handover_date"]["values"] if str(x["raw"]) == r] for r in ("2028-12-31", "2029-03-31")]}
    assert handover == {("brochure", "regulator_filing", "spa"), ("crm_export",)}
