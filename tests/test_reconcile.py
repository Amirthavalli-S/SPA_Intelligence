"""Reconciliation: the current terms of one agreement after amendments. Pure logic, no model, no API."""
import random
from datetime import date

from app.reconcile import Doc, fields_from_contract, reconcile
from tests.fakes import oracle_input
from pathlib import Path

PLAN = [{"name": "On booking", "percent": 20.0, "due_date": "2025-01-14"}, {"name": "On handover", "percent": 80.0, "due_date": None}]
RATE = {"rate": 10.0, "basis": "fixed_per_sqft_per_month"}

# AGR-1105 as described in the demo story: the SPA states everything; each later document states only what it changes.
SPA = Doc("spa", "AGR-1105 SPA", "SPA", date(2025, 1, 14),
          {"price": 10_000_000.0, "possession_date": "2028-12-31", "payment_schedule": PLAN, "penalty_rate": RATE, "grace_period_days": 0})
ADD1 = Doc("add1", "Addendum 1", "Addendum", date(2026, 3, 10), {"price": 9_500_000.0})
ADD2 = Doc("add2", "Extension Letter", "Extension Letter", date(2026, 7, 18), {"possession_date": "2029-06-30"})


def test_amendments_change_only_what_they_state():
    r = reconcile("AGR-1105", [SPA, ADD1, ADD2])
    c = r["current"]
    assert c["price"] == 9_500_000.0 and c["possession_date"] == "2029-06-30"
    assert c["payment_schedule"] == PLAN and c["payment_plan_version"] == 1          # untouched by both amendments
    assert c["penalty_rate"] == RATE and c["grace_period_days"] == 0
    assert r["problems"] == [] and r["missing"] == ["penalty_cap"]


def test_each_value_names_the_document_it_came_from():
    s = reconcile("AGR-1105", [SPA, ADD1, ADD2])["sources"]
    assert s["price"]["doc_id"] == "add1" and s["possession_date"]["doc_id"] == "add2" and s["penalty_rate"]["doc_id"] == "spa"


def test_timeline_lists_what_each_document_changed_in_date_order():
    t = reconcile("AGR-1105", [SPA, ADD1, ADD2])["timeline"]
    assert [x["doc_type"] for x in t] == ["SPA", "Addendum", "Extension Letter"]
    assert [x["date"] for x in t] == ["2025-01-14", "2026-03-10", "2026-07-18"]
    assert {c["field"] for c in t[0]["changes"]} == {"price", "possession_date", "payment_schedule", "penalty_rate", "grace_period_days"}
    assert t[1]["changes"] == [{"field": "price", "kind": "changed", "from": 10_000_000.0, "to": 9_500_000.0}]
    assert t[2]["changes"] == [{"field": "possession_date", "kind": "changed", "from": "2028-12-31", "to": "2029-06-30"}]


def test_the_order_documents_are_passed_in_does_not_matter():
    expected = reconcile("A", [SPA, ADD1, ADD2])
    for seed in range(6):
        docs = [SPA, ADD1, ADD2]
        random.Random(seed).shuffle(docs)
        assert reconcile("A", docs) == expected | {"documents": [{"doc_id": d.doc_id, "name": d.name, "doc_type": d.doc_type,
                                                                   "date_signed": d.date_signed.isoformat()} for d in docs]}


def test_last_writer_wins_even_when_an_older_document_is_uploaded_later():
    later = Doc("x", "Addendum 2", "Addendum", date(2026, 9, 1), {"price": 9_000_000.0})
    r = reconcile("A", [later, SPA, ADD1])                    # uploaded out of order
    assert r["current"]["price"] == 9_000_000.0


def test_restating_a_value_is_not_a_change():
    again = Doc("again", "Addendum", "Addendum", date(2026, 1, 1), {"price": 10_000_000.0, "possession_date": "2028-12-31"})
    t = reconcile("A", [SPA, again])["timeline"]
    assert t[1]["changes"] == []


def test_a_changed_payment_schedule_bumps_the_plan_version():
    new_plan = [{"name": "On booking", "percent": 10.0, "due_date": None}, {"name": "On handover", "percent": 90.0, "due_date": None}]
    r = reconcile("A", [SPA, Doc("p", "Addendum", "Addendum", date(2026, 2, 1), {"payment_schedule": new_plan})])
    assert r["current"]["payment_schedule"] == new_plan and r["current"]["payment_plan_version"] == 2


def test_same_day_documents_apply_spa_then_addendum():
    spa = Doc("s", "SPA", "SPA", date(2026, 1, 1), {"price": 1.0})
    add = Doc("a", "Addendum", "Addendum", date(2026, 1, 1), {"price": 2.0})
    assert reconcile("A", [add, spa])["current"]["price"] == 2.0


def test_documents_that_cannot_be_ordered_or_belong_to_the_project_are_reported_not_merged():
    undated = Doc("u", "Undated addendum", "Addendum", None, {"price": 1.0})
    filing = Doc("f", "RERA filing", "RERA Filing", date(2025, 1, 1), {"possession_date": "2028-12-31"})
    r = reconcile("A", [SPA, undated, filing])
    assert r["current"]["price"] == 10_000_000.0                       # neither changed anything
    assert len(r["problems"]) == 2 and "no signing date" in r["problems"][0] and "project" in r["problems"][1]


def test_no_documents_gives_an_empty_state():
    r = reconcile("A", [])
    assert r["timeline"] == [] and r["current"] == {"payment_plan_version": 1} and set(r["missing"]) >= {"price", "possession_date"}


def test_fields_from_contract_leaves_out_what_the_document_does_not_state():
    from app.extract import extract_from_llm, pdf_pages, postprocess
    from app.schema import ContractData
    from tests.fakes import FakeClient
    p = Path("samples/sample_a.pdf"); b = p.read_bytes()
    c = postprocess(ContractData(**extract_from_llm(b, FakeClient(oracle_input(p))).model_dump()), pdf_pages(b), b)
    f = fields_from_contract(c)
    assert f["price"] == 2_450_000.0 and f["possession_date"] == "2027-06-30" and len(f["payment_schedule"]) == 5
    c.price.value = None
    assert "price" not in fields_from_contract(c)
