"""The human-review gate: only contracts whose flagged values have all been reviewed become 'approved' in Supabase,
and buyers get no answers from a contract that is still waiting for review."""
import json

import pytest
from fastapi.testclient import TestClient

from app.extract import extract_contract
from backend.api import persistence
from backend.api.main import create_app
from backend.tests.test_api import SAMPLES, FakeClient, env, oracle_input, seeded, sid  # noqa: F401
from backend.tests.test_database import pg, q  # noqa: F401  (pg fixture)
from backend.tests.test_database import pytestmark  # noqa: F401

A = sid("sample_a.pdf")
REV = "reviewer-key-" + "b" * 20
BUYER = "tok-buyer-a-123"


@pytest.fixture
def flagged(env, seeded):  # noqa: F811
    """sample_a re-extracted with one value the grounding check can only half confirm, so it needs a human."""
    p = SAMPLES / "sample_a.pdf"
    inp = oracle_input(p)
    inp["delay_cap"]["source_quote"] = inp["delay_cap"]["source_quote"].replace("shall not exceed", "shall never exceed")
    extract_contract(p.read_bytes(), p.name, client=FakeClient(inp), use_cache=False)


@pytest.fixture
def api(flagged, pg, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setenv("AUTH_MODE", "apikey")
    monkeypatch.setenv("API_KEYS", json.dumps({REV: {"name": "Rita Reviewer", "roles": ["Spa.Reviewer"]}}))
    monkeypatch.setenv("SPA_AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setenv("SPA_NOTIFY_STATE", str(tmp_path / "notified.json"))
    with TestClient(create_app()) as c:
        yield c


H = {"X-API-Key": REV}


def approved_ids():
    return {r[0] for r in q("select contract_id from approved_contracts")}


def test_flagged_contract_is_not_approved_and_review_open_is_counted(api):
    persistence.sync_contracts()
    assert A not in approved_ids()                                     # the draft stays out of the approved table
    assert q("select review_open from contracts where id = %s", (A,))[0][0] >= 1     # the count used to be stuck at 0
    assert sid("sample_b.pdf") in approved_ids()                       # nothing flagged: approved automatically


def test_reviewing_every_flagged_value_approves_it_with_the_reviewed_data(api):
    items = [i for i in api.get("/api/review-queue", headers=H).json()["items"] if i["contract_id"] == A]
    assert items
    for it in items:
        r = api.post(f"/api/contracts/{A}/fields/{it['field']}/review",
                     json={"action": "correct", "value": 7.5, "reviewer": "Rita"}, headers=H) \
            if it["field"] == "delay_cap" else \
            api.post(f"/api/contracts/{A}/fields/{it['field']}/review", json={"action": "accept", "reviewer": "Rita"}, headers=H)
        assert r.status_code == 200, r.text
    persistence.sync_contracts()
    assert A in approved_ids()
    who, data = q("select approved_by, data from approved_contracts where contract_id = %s", (A,))[0]
    assert who == "Rita Reviewer"                                  # taken from the signed-in account
    assert data["delay_cap"]["value"] == 7.5 and data["delay_cap"]["human_verified"] is True
    assert q("select review_open from contracts where id = %s", (A,))[0][0] == 0


def test_a_contract_is_unapproved_again_when_it_is_re_extracted_with_flags(api):
    persistence.sync_contracts()
    q("insert into approved_contracts (contract_id, name, data) values (%s, 'x', '{}'::jsonb) on conflict do nothing", (A,))
    persistence.sync_contracts()
    assert A not in approved_ids()                                     # a stale approval is removed, never kept


def test_buyer_chat_waits_for_review(api, monkeypatch):
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("BUYER_TOKENS", json.dumps({BUYER: A}))
    with TestClient(create_app()) as c:
        r = c.post("/api/buyer/chat", json={"message": "When is my next payment?"}, headers={"Authorization": f"Bearer {BUYER}"})
        assert r.status_code == 409 and r.json()["error"]["code"] == "pending_review"
        monkeypatch.setenv("REQUIRE_REVIEW", "0")                       # explicit opt-out for demos
        r2 = c.post("/api/buyer/chat", json={"message": "Can I cancel and get a refund?"}, headers={"Authorization": f"Bearer {BUYER}"})
        assert r2.status_code != 409
