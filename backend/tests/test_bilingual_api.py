from pathlib import Path

from backend.tests.test_api import client, env  # noqa: F401

S = Path("samples")




def first_id(client):
    return client.get("/api/contracts").json()[0]["id"]


def test_sample_pair_returns_the_planted_mismatch(client):  # noqa: F811
    cid = first_id(client)
    r = client.post(f"/api/contracts/{cid}/bilingual-check?sample=pair_1")
    assert r.status_code == 200
    j = r.json()
    assert j["summary"]["mismatch"] == 1 and "not legal advice" in j["disclaimer"]


def test_uploaded_arabic_pdf_is_compared_with_the_contract(client):  # noqa: F811
    cid = first_id(client)
    ar = Path("samples/bilingual/pair_1/ar.pdf").read_bytes()
    r = client.post(f"/api/contracts/{cid}/bilingual-check", files={"arabic": ("ar.pdf", ar, "application/pdf")})
    assert r.status_code == 200 and "pairs" in r.json()


def test_missing_or_bad_input_is_refused(client):  # noqa: F811
    cid = first_id(client)
    assert client.post(f"/api/contracts/{cid}/bilingual-check").status_code == 422
    r = client.post(f"/api/contracts/{cid}/bilingual-check", files={"arabic": ("x.pdf", b"hello", "application/pdf")})
    assert r.status_code == 415
    assert client.post(f"/api/contracts/{cid}/bilingual-check?sample=nope").status_code == 404
    assert client.post("/api/contracts/" + "0" * 64 + "/bilingual-check?sample=pair_1").status_code == 404
