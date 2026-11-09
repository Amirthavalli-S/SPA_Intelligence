"""effective_contracts in the real database follows the agreements the app computes."""
import pytest
from fastapi.testclient import TestClient

from backend.api import persistence
from backend.api.main import create_app
from backend.tests.test_api import env, seeded, sid  # noqa: F401
from backend.tests.test_database import pg, q  # noqa: F401  (pg fixture)
from backend.tests.test_database import pytestmark  # noqa: F401

A, B = sid("sample_a.pdf"), sid("sample_b.pdf")


@pytest.fixture
def api(env, seeded, pg, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setenv("SPA_NOTIFY_STATE", str(tmp_path / "notified.json"))
    with TestClient(create_app()) as c:
        yield c


def test_the_effective_terms_are_saved_and_removed_with_the_agreement(api):
    api.put(f"/api/contracts/{A}/agreement", json={"agreement_id": "AGR-T1", "doc_type": "SPA", "date_signed": "2025-01-14"})
    api.put(f"/api/contracts/{B}/agreement", json={"agreement_id": "AGR-T1", "doc_type": "Addendum", "date_signed": "2026-03-10"})
    persistence.sync_contracts()
    price_b = api.get(f"/api/contracts/{B}").json()["contract"]["price"]["value"]
    price, version, docs, timeline = q("select price, payment_plan_version, documents, timeline from effective_contracts where agreement_id = 'AGR-T1'")[0]
    assert float(price) == price_b and version >= 1 and len(docs) == 2 and [t["doc_type"] for t in timeline] == ["SPA", "Addendum"]
    assert q("select agreement_id, doc_type, date_signed::text from contracts where id = %s", (B,)) == [("AGR-T1", "Addendum", "2026-03-10")]
    api.put(f"/api/contracts/{A}/agreement", json={})
    api.put(f"/api/contracts/{B}/agreement", json={})
    persistence.sync_contracts()
    assert q("select count(*) from effective_contracts where agreement_id = 'AGR-T1'")[0][0] == 0
