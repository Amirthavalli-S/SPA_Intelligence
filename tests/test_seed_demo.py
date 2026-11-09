"""scripts/seed_demo.py loads the Green Valley story with no model, through the real grounding checks."""
import importlib.util
from pathlib import Path

from app import config, crossdoc as cd
from app.extract import load_cached


def load_script():
    spec = importlib.util.spec_from_file_location("seed_demo", Path("scripts/seed_demo.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_seeding_makes_the_four_documents_and_the_project_documents_available_offline(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    out = load_script().seed(log=lambda *_: None)
    assert out == {"contracts": 4, "facts": 2}
    for name in ("pgv_agr1105_spa", "pgv_agr1105_addendum1", "pgv_agr1105_extension", "pgv_agr1108_spa"):
        c = load_cached((Path("samples") / f"{name}.pdf").read_bytes())
        assert c is not None and not [w for w in c.warnings if "ungrounded" in w]          # the real checks ran and nothing was withheld
    assert load_cached(Path("samples/pgv_agr1105_spa.pdf").read_bytes()).price.value == 10_000_000
    brochure = cd.load_facts_cached(Path("samples/crossdoc/set_4_pgv/brochure.pdf").read_bytes())
    assert brochure.handover_date.value.isoformat() == "2028-12-31" and brochure.registration_number.value == "TN/29/Building/0234/2025"
    assert brochure.price.value is None                                                      # "starting from" is not this unit's price


def test_seeding_is_repeatable(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    s = load_script()
    assert s.seed(log=lambda *_: None) == s.seed(log=lambda *_: None)
