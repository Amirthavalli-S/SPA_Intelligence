"""Departments: one policy table decides what each team's staff may call, and what Sales never receives."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from app import departments
from backend.api.main import create_app
from backend.tests.test_api import env, seeded, sid  # noqa: F401

A = sid("sample_a.pdf")
CID = "a" * 64


# ------------------------------------------------------------------ the policy table itself
def test_each_department_gets_only_its_own_features():
    assert departments.features("legal") == {"terms", "gap", "playbook", "crosscheck", "obligations", "agreements", "bilingual"}
    assert departments.features("finance") == {"penalty", "cashflow"}
    assert departments.features("sales") == {"terms"}
    assert departments.features("management") == {"accuracy", "obligations"}
    assert departments.features(None) is None                       # no department: the older behaviour, nothing extra is refused


def test_each_department_has_its_own_home_and_none_shares_one():
    homes = {d: departments.home(d) for d in departments.DEPARTMENTS}
    assert homes == {"legal": "/app/legal", "finance": "/app/finance", "sales": "/app/sales", "management": "/app/management"}
    assert len(set(homes.values())) == 4 and departments.home(None) is None


@pytest.mark.parametrize("dept, path, ok", [
    ("finance", f"/api/contracts/{CID}/penalty", True), ("finance", f"/api/contracts/{CID}/cashflow", True),
    ("finance", f"/api/contracts/{CID}/statute-gap", False), ("finance", f"/api/contracts/{CID}/playbook", False),
    ("finance", "/api/crossdoc/sets", False), ("finance", "/api/eval/results", False), ("finance", "/api/obligations", False),
    ("legal", f"/api/contracts/{CID}/statute-gap", True), ("legal", f"/api/contracts/{CID}/playbook", True),
    ("legal", "/api/crossdoc/sets", True), ("legal", f"/api/contracts/{CID}/penalty", False), ("legal", f"/api/contracts/{CID}/cashflow", False),
    ("legal", "/api/agreements/AGR-1", True), ("legal", "/api/eval/results", False),
    ("sales", f"/api/contracts/{CID}", True), ("sales", f"/api/contracts/{CID}/penalty", False), ("sales", f"/api/contracts/{CID}/chat", False),
    ("sales", "/api/agreements/AGR-1", False), ("sales", "/api/review-queue", False), ("sales", "/api/obligations", False),
    ("management", "/api/eval/results", True), ("management", "/api/obligations", True), ("management", "/api/alerts", True),
    ("management", f"/api/contracts/{CID}/penalty", False), ("management", f"/api/contracts/{CID}/cashflow", False),
    ("management", "/api/crossdoc/sets", False), ("management", "/api/buyers", False),
    (None, f"/api/contracts/{CID}/penalty", True), (None, "/api/eval/results", True),
])
def test_what_each_department_may_call(dept, path, ok):
    assert departments.allows(dept, path) is ok


EXPECTED_BASE = {
    "GET /api/auth/config", "GET /api/auth/github/callback", "GET /api/auth/github/login", "POST /api/auth/logout", "GET /api/auth/me",
    "POST /api/auth/supabase/login", "POST /api/auth/supabase/recover", "POST /api/auth/supabase/reset", "POST /api/auth/supabase/signup",
    "POST /api/buyer/chat", "GET /api/buyer/me", "GET /api/contracts", "POST /api/contracts/upload", "GET /api/contracts/{contract_id}",
    "GET /api/contracts/{contract_id}/evidence/{field}", "POST /api/contracts/{contract_id}/extract",
    "POST /api/contracts/{contract_id}/fields/{field}/review", "PUT /api/contracts/{contract_id}/jurisdiction",
    "GET /api/contracts/{contract_id}/locate", "GET /api/contracts/{contract_id}/page/{page}.png", "GET /api/contracts/{contract_id}/pdf",
    "GET /api/contracts/{contract_id}/status", "GET /api/health", "GET /api/packs", "GET /api/simulation/defaults",
    "GET /api/users", "PUT /api/users/{user_id}/role",
}


def test_every_route_is_either_restricted_to_a_feature_or_on_the_reviewed_shared_list():
    """If this fails you added a route: decide which department feature it belongs to (app/departments.py RESTRICTED), or, if every
    department may use it, add it to EXPECTED_BASE here. A new financial route must never be open to Sales by default."""
    unclassified = set()
    for path, ops in create_app().openapi()["paths"].items():
        concrete = re.sub(r"\{[^}]+\}", "x", path.replace("{contract_id}", CID))
        if departments.feature_of(concrete) is None:
            unclassified |= {f"{m.upper()} {path}" for m in ops}
    assert unclassified == EXPECTED_BASE


# ------------------------------------------------------------------ through the API
def keys(**extra):
    out = {}
    for name, dept in (("legal", "legal"), ("finance", "finance"), ("sales", "sales"), ("mgmt", "management"), ("plain", None)):
        out[f"{name}-key-" + "x" * 20] = {"name": name.title(), "roles": ["Spa.Staff"], **({"department": dept} if dept else {})}
    out["rev-key-" + "r" * 20] = {"name": "Rita", "roles": ["Spa.Reviewer"], "department": "sales"}      # cross-cutting: department ignored
    return out | extra


KEY = {k.split("-key-")[0]: k for k in keys()}


@pytest.fixture
def api(env, seeded, monkeypatch):  # noqa: F811
    monkeypatch.setenv("AUTH_MODE", "apikey")
    monkeypatch.setenv("API_KEYS", json.dumps(keys()))
    return TestClient(create_app())


def H(who):
    return {"X-API-Key": KEY[who]}


def test_finance_can_simulate_but_not_read_legal_or_management_data(api):
    assert api.post(f"/api/contracts/{A}/penalty", json={}, headers=H("finance")).status_code == 200
    assert api.post(f"/api/contracts/{A}/cashflow", json={}, headers=H("finance")).status_code == 200
    for method, path in (("post", f"/api/contracts/{A}/statute-gap"), ("get", f"/api/contracts/{A}/playbook"), ("get", "/api/crossdoc/sets"),
                         ("get", "/api/eval/results"), ("get", "/api/obligations")):
        r = getattr(api, method)(path, headers=H("finance"), **({"json": {"delay_days": 90}} if method == "post" else {}))
        assert r.status_code == 403 and "department" in r.json()["error"]["message"], path


def test_legal_cannot_run_the_money_simulators(api):
    assert api.get(f"/api/contracts/{A}/playbook", headers=H("legal")).status_code == 200
    assert api.get("/api/crossdoc/sets", headers=H("legal")).status_code == 200
    assert api.post(f"/api/contracts/{A}/penalty", json={}, headers=H("legal")).status_code == 403
    assert api.post(f"/api/contracts/{A}/cashflow", json={}, headers=H("legal")).status_code == 403


def test_management_sees_accuracy_and_obligations_only(api):
    assert api.get("/api/eval/results", headers=H("mgmt")).status_code in (200, 404)           # allowed (404 = no run saved yet)
    assert api.get("/api/obligations", headers=H("mgmt")).status_code == 200
    assert api.post(f"/api/contracts/{A}/penalty", json={}, headers=H("mgmt")).status_code == 403
    assert api.get("/api/crossdoc/sets", headers=H("mgmt")).status_code == 403


def test_sales_never_receives_the_price_or_the_delay_exposure_terms(api):
    full = api.get(f"/api/contracts/{A}", headers=H("plain")).json()
    assert full["contract"]["price"]["value"] == 2450000 and full["plan"][0]["amount"] == 490000 and full["restricted_fields"] == []
    r = api.get(f"/api/contracts/{A}", headers=H("sales")).json()
    c = r["contract"]
    for f in ("price", "delay_rate", "delay_basis", "delay_cap"):
        assert c[f]["value"] is None and c[f]["source_quote"] is None and not c[f].get("evidence"), f
    assert c["buyer"]["value"] == "Layla Hassan Al Mansoori" and c["handover_date"]["value"] == "2027-06-30"      # the rest is still there
    assert [p["amount"] for p in r["plan"]] == [None] * 5 and r["plan"][0]["percent"] == 20.0 and r["plan"][0]["due_date"]
    assert set(r["restricted_fields"]) >= {"price", "delay_rate", "delay_cap", "plan_amounts"}
    assert all(m["source_quote"] == "-" for m in c["payment_plan"])                           # row quotes carry amounts
    assert "2,450,000" not in json.dumps(r) and "490,000" not in json.dumps(r)


def test_sales_list_has_no_prices_and_cannot_open_evidence_for_restricted_values(api):
    assert all(c["price"] is None for c in api.get("/api/contracts", headers=H("sales")).json())
    assert any(c["price"] for c in api.get("/api/contracts", headers=H("plain")).json())
    assert api.get(f"/api/contracts/{A}/evidence/price", headers=H("sales")).status_code == 403
    assert api.get(f"/api/contracts/{A}/evidence/delay_rate", headers=H("sales")).status_code == 403
    assert api.get(f"/api/contracts/{A}/evidence/payment_plan.1", headers=H("sales")).status_code == 403
    assert api.get(f"/api/contracts/{A}/evidence/buyer", headers=H("sales")).status_code == 200
    assert api.get(f"/api/contracts/{A}/evidence/price", headers=H("legal")).status_code == 200


def test_a_staff_account_with_no_department_keeps_the_older_full_read_access(api):
    for method, path in (("get", f"/api/contracts/{A}/playbook"), ("get", "/api/crossdoc/sets"), ("get", "/api/obligations")):
        assert getattr(api, method)(path, headers=H("plain")).status_code == 200


def test_reviewers_are_cross_cutting_so_a_department_on_their_key_changes_nothing(api):
    assert api.post(f"/api/contracts/{A}/penalty", json={}, headers=H("rev")).status_code == 200
    assert api.get(f"/api/contracts/{A}", headers=H("rev")).json()["contract"]["price"]["value"] == 2450000


def test_who_am_i_tells_the_browser_the_department_and_its_features(api):
    me = api.get("/api/auth/me", headers=H("finance")).json()
    assert me["department"] == "finance" and me["features"] == ["cashflow", "penalty"] and me["redacted"] is False
    s = api.get("/api/auth/me", headers=H("sales")).json()
    assert s["department"] == "sales" and s["features"] == ["terms"] and s["redacted"] is True
    p = api.get("/api/auth/me", headers=H("plain")).json()
    assert p["department"] is None and p["features"] is None
