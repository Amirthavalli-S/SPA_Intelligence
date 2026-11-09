"""Agreements over the API: group documents, merge them, and who is allowed to do what."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.tests.test_api import client, env, seeded, sid  # noqa: F401

A, B, C = sid("sample_a.pdf"), sid("sample_b.pdf"), sid("sample_c.pdf")


def link(client, cid, aid="AGR-T1", doc_type="SPA", signed="2025-01-14"):
    return client.put(f"/api/contracts/{cid}/agreement", json={"agreement_id": aid, "doc_type": doc_type, "date_signed": signed})


def test_documents_of_one_agreement_are_merged_by_signing_date(client, seeded):
    assert link(client, A).status_code == 200
    assert link(client, B, doc_type="Addendum", signed="2026-03-10").status_code == 200
    r = client.get("/api/agreements/AGR-T1").json()
    assert [t["doc_type"] for t in r["timeline"]] == ["SPA", "Addendum"]
    spa, add = r["timeline"][0], r["timeline"][1]
    assert spa["doc_id"] == A and add["doc_id"] == B
    assert r["current"]["price"] == client.get(f"/api/contracts/{B}").json()["contract"]["price"]["value"]   # the later document wins
    assert r["sources"]["price"]["doc_id"] == B
    assert r["pending_review"] == 0 and r["problems"] == []
    assert {d["doc_id"] for d in r["documents"]} == {A, B}


def test_the_contract_list_carries_the_agreement_and_clearing_it_removes_the_agreement(client, seeded):
    link(client, A)
    row = next(c for c in client.get("/api/contracts").json() if c["id"] == A)
    assert row["agreement_id"] == "AGR-T1" and row["doc_type"] == "SPA" and row["date_signed"] == "2025-01-14"
    mine = lambda: [a for a in client.get("/api/agreements").json() if a["agreement_id"] == "AGR-T1"]  # noqa: E731  (the Green Valley samples bring their own)
    assert mine() == [{"agreement_id": "AGR-T1", "documents": 1, "latest_signed": "2025-01-14"}]
    assert client.put(f"/api/contracts/{A}/agreement", json={}).status_code == 200
    assert mine() == []
    assert client.get("/api/agreements/AGR-T1").status_code == 404


def test_an_undated_document_is_reported_not_silently_merged(client, seeded):
    link(client, A)
    link(client, B, doc_type="Addendum", signed=None)
    r = client.get("/api/agreements/AGR-T1").json()
    assert any("no signing date" in p for p in r["problems"])
    assert r["sources"]["price"]["doc_id"] == A


@pytest.mark.parametrize("body", [{"agreement_id": "has space"}, {"agreement_id": "x" * 41}, {"agreement_id": "A1", "doc_type": "Memo"},
                                   {"agreement_id": "A1", "date_signed": "10-03-2026"}, {"agreement_id": "A1", "date_signed": "1850-01-01"}])
def test_bad_agreement_data_is_refused(client, seeded, body):
    assert client.put(f"/api/contracts/{A}/agreement", json=body).status_code == 422


def test_unknown_contract_and_agreement(client, seeded):
    assert client.put(f"/api/contracts/{'0' * 64}/agreement", json={"agreement_id": "A1"}).status_code == 404
    assert client.get("/api/agreements/NOPE").status_code == 404
    assert client.get("/api/agreements/bad id!").status_code == 404


def test_sample_defaults_apply_until_a_person_saves_a_choice(client, seeded, monkeypatch, tmp_path):
    from app import config
    d = tmp_path / "samples"; d.mkdir()
    for p in config.SAMPLES_DIR.glob("*.pdf"):
        (d / p.name).write_bytes(p.read_bytes())
    (d / "agreements.json").write_text(json.dumps({"sample_a.pdf": {"agreement_id": "AGR-D", "doc_type": "SPA", "date_signed": "2025-02-02"}}))
    monkeypatch.setattr(config, "SAMPLES_DIR", d)
    assert next(c for c in client.get("/api/contracts").json() if c["id"] == A)["agreement_id"] == "AGR-D"
    link(client, A, aid="AGR-OTHER")
    assert next(c for c in client.get("/api/contracts").json() if c["id"] == A)["agreement_id"] == "AGR-OTHER"


REV, STAFF = "reviewer-key-" + "b" * 20, "staff-key-" + "a" * 20


@pytest.fixture
def secure(env, seeded, monkeypatch):  # noqa: F811
    monkeypatch.setenv("AUTH_MODE", "apikey")
    monkeypatch.setenv("API_KEYS", json.dumps({STAFF: {"name": "Sam", "roles": ["Spa.Staff"]}, REV: {"name": "Rita Reviewer", "roles": ["Spa.Reviewer"]}}))
    return TestClient(create_app())


def test_staff_can_read_agreements_but_only_a_reviewer_can_change_them(secure):
    body = {"agreement_id": "AGR-T1", "doc_type": "SPA", "date_signed": "2025-01-14"}
    assert secure.put(f"/api/contracts/{A}/agreement", json=body, headers={"X-API-Key": STAFF}).status_code == 403
    assert secure.put(f"/api/contracts/{A}/agreement", json=body, headers={"X-API-Key": REV}).status_code == 200
    assert secure.get("/api/agreements/AGR-T1", headers={"X-API-Key": STAFF}).status_code == 200
    assert secure.get("/api/agreements/AGR-T1").status_code == 401


def test_the_agreement_endpoints_are_not_open_to_buyers(env, seeded, monkeypatch):  # noqa: F811
    monkeypatch.setenv("AUTH_MODE", "apikey")
    monkeypatch.setenv("API_KEYS", json.dumps({"buyer-key-" + "c" * 20: {"name": "Bo", "roles": ["Spa.Buyer"], "contract_id": A}}))
    c = TestClient(create_app())
    assert c.get("/api/agreements", headers={"X-API-Key": "buyer-key-" + "c" * 20}).status_code == 403
