"""The Green Valley story end to end through the API, with no model call: the documents group themselves, merge, cross-check and get judged."""
import json
from pathlib import Path

import pytest

from app import config
from app import crossdoc as cd
from app.extract import extract_contract, file_hash
from backend.tests.test_api import client, env  # noqa: F401
from eval.labels import labels_to_tool_input
from tests.fakes import FakeClient
from tests.test_crossdoc import facts_oracle

SAMPLES, SET = Path("samples"), Path("samples/crossdoc/set_4_pgv")
NAMES = {"pgv_agr1105_spa": "pgv_agr1105_spa.pdf", "pgv_agr1105_addendum1": "pgv_agr1105_addendum1.pdf",
         "pgv_agr1105_extension": "pgv_agr1105_extension.pdf", "pgv_agr1108_spa": "pgv_agr1108_spa.pdf"}


def cid(doc_id):
    return file_hash((SAMPLES / NAMES[doc_id]).read_bytes())


@pytest.fixture
def story(env):  # noqa: F811
    for doc_id, name in NAMES.items():
        labels = json.loads((Path("eval/golden") / doc_id / "labels.json").read_text())
        extract_contract((SAMPLES / name).read_bytes(), name, client=FakeClient(labels_to_tool_input(labels)))
    provider = facts_oracle(SET)                          # stands in for the model reading the brochure and the filing
    for d in cd.load_set(SET).documents:
        if d.type in ("brochure", "regulator_filing"):
            pdf = Path(d.path).read_bytes()
            cd.facts_cache_path(pdf).parent.mkdir(parents=True, exist_ok=True)
            cd.facts_cache_path(pdf).write_text(json.dumps({"model": config.model_tag(), "facts": json.loads(provider(d).model_dump_json())}))


def test_the_sample_documents_group_into_two_agreements_by_themselves(client, story):
    ag = {a["agreement_id"]: a for a in client.get("/api/agreements").json()}
    assert ag["AGR-1105"]["documents"] == 3 and ag["AGR-1108"]["documents"] == 1
    assert ag["AGR-1105"]["latest_signed"] == "2026-07-18"


def test_agr_1105_reconciles_to_the_promised_effective_state(client, story):
    r = client.get("/api/agreements/AGR-1105").json()
    c = r["current"]
    assert c["price"] == 9_500_000 and c["possession_date"] == "2029-06-30" and c["payment_plan_version"] == 1
    assert c["penalty_rate"] == {"rate": 10.0, "basis": "fixed_per_sqft_per_month"} and r["currency"] == "INR"
    assert [t["doc_type"] for t in r["timeline"]] == ["SPA", "Addendum", "Extension Letter"]
    assert r["sources"]["price"]["name"] == "pgv_agr1105_addendum1.pdf" and r["sources"]["possession_date"]["doc_type"] == "Extension Letter"
    assert r["problems"] == [] and r["pending_review"] == 0


def test_the_cross_check_shows_the_three_way_possession_mismatch(client, story):
    assert "set_4_pgv" in [s["set_id"] for s in client.get("/api/crossdoc/sets").json()["sets"]]
    r = client.get("/api/crossdoc/sets/set_4_pgv").json()
    assert [c["attribute"] for c in r["conflicts"]] == ["handover_date"]
    assert sorted({str(v["raw"]) for v in r["conflicts"][0]["values"]}) == ["2028-12-31", "2029-03-31", "2029-06-30"]
    assert r["planted_score"]["precision"] == 1.0 and r["planted_score"]["recall"] == 1.0 and not r["pending"]
    assert {d["type"]: d["match"] for d in r["documents"]}["regulator_filing"] == "project"


def test_the_rulebook_flags_agr_1108_and_clears_agr_1105(client, story):
    def gv(doc_id):
        rows = client.get(f"/api/contracts/{cid(doc_id)}/playbook").json()["results"]
        return {r["rule_id"]: r["status"] for r in rows if r["rule_id"].startswith("gv_")}
    assert set(gv("pgv_agr1105_spa").values()) == {"pass"} and len(gv("pgv_agr1105_spa")) == 5
    assert gv("pgv_agr1108_spa") == {"gv_postponement_max": "fail", "gv_min_rate": "fail", "gv_refund_required": "fail",
                                     "gv_force_majeure_required": "pass", "gv_rera_matches": "pass"}
    assert gv("pgv_agr1105_addendum1") == {}                       # an addendum is not judged as if it were an SPA


def test_the_demo_penalty_matches_the_hand_calculation_through_the_api(client, story):
    r = client.post(f"/api/contracts/{cid('pgv_agr1105_spa')}/penalty", json={"scenarios": [90]}).json()
    assert r["rows"][0]["penalty"] == 34027.4
    assert r["terms"]["basis"]["value"] == "fixed_per_sqft_per_month"
