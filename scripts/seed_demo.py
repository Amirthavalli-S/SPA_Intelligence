"""Load the Green Valley demo story into the app WITHOUT calling a model.

    python scripts/seed_demo.py

Each demo document's labels (the truth by construction) are treated as if the model had read it, then the REAL grounding checks run
against the PDF and the result is cached, so the contract list shows the four documents as already extracted. The brochure and the RERA
filing are seeded the same way for the cross-document check. This is for demonstrations of synthetic data only: it never touches an
uploaded contract, and a real extraction (Extract button) replaces it. Needs no key.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config, crossdoc as cd  # noqa: E402
from app.extract import extract_contract, locate_quote, pdf_pages  # noqa: E402
from eval.labels import labels_to_tool_input  # noqa: E402

DOCS = {"pgv_agr1105_spa": "pgv_agr1105_spa.pdf", "pgv_agr1105_addendum1": "pgv_agr1105_addendum1.pdf",
        "pgv_agr1105_extension": "pgv_agr1105_extension.pdf", "pgv_agr1108_spa": "pgv_agr1108_spa.pdf"}
SET = ROOT / "samples" / "crossdoc" / "set_4_pgv"


class _OfflineModel:
    """Answers the model call with what the labels say (the same shape the test stub uses). Only this script uses it."""

    def __init__(self, tool_input: dict):
        from types import SimpleNamespace
        self._in, self._ns = tool_input, SimpleNamespace
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **_kw):
        return self._ns(content=[self._ns(type="tool_use", name="record_contract_terms", id="demo_seed", input=self._in)])


def seed(log=print) -> dict:
    out = {"contracts": 0, "facts": 0}
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for doc_id, fname in DOCS.items():
        labels = json.loads((ROOT / "eval" / "golden" / doc_id / "labels.json").read_text(encoding="utf-8"))
        pdf = (ROOT / "samples" / fname).read_bytes()
        c = extract_contract(pdf, fname, client=_OfflineModel(labels_to_tool_input(labels)), use_cache=False)
        out["contracts"] += 1
        log(f"  {fname}: seeded ({len(c.warnings)} warning(s), {sum(1 for _ in c.payment_plan)} plan rows)")
    facts = json.loads((SET / "facts.json").read_text(encoding="utf-8"))
    for ref in cd.load_set(SET).documents:
        if ref.type not in ("brochure", "regulator_filing"):
            continue
        entry = facts["brochure" if ref.type == "brochure" else "filing"]
        pdf = Path(ref.path).read_bytes()
        pages = pdf_pages(pdf)

        def S(attr):
            q, v = entry["quotes"].get(attr), entry["values"].get(attr)
            return {"value": v, "source_page": locate_quote(pages, q) if q and v is not None else None, "source_quote": q if v is not None else None}
        tool_input = {a: S(a) for a in ("unit_id", "price", "area_sqft", "handover_date", "payment_plan", "delay_rate", "registration_number")}
        cd.extract_facts_cached(pdf, _OfflineModel(tool_input))
        out["facts"] += 1
        log(f"  {ref.name}: facts seeded for the cross-document check")
    return out


def main() -> int:
    print("Seeding the Green Valley demo (synthetic data, no model call)...")
    r = seed()
    print(f"Done: {r['contracts']} contracts and {r['facts']} project documents. Open the app, then Agreements -> AGR-1105, "
          f"and Cross-check -> set_4_pgv.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
