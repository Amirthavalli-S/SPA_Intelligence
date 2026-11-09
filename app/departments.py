"""Departments: what each team can see. One table, used by the server (to refuse) and sent to the browser (to show only what is allowed).

A department is a property of a STAFF account, set only by an administrator (never chosen by the person signing in). Reviewers and
admins are cross-cutting roles and have no department. A staff account with no department keeps the older behaviour (all read features).

A "feature" is a group of server routes. Routes not listed in RESTRICTED (the contract list and detail, status, PDF and page
images, packs) are the shared base every department needs. The PDF itself shows whatever is printed in it; the data restrictions
below apply to the structured values and calculators, not to the document a person is allowed to open.
"""
from __future__ import annotations

import re
from typing import Any

DEPARTMENTS = ("legal", "finance", "sales", "management")

POLICY: dict[str, dict[str, Any]] = {
    "legal": {"home": "/app/legal", "features": {"terms", "gap", "playbook", "crosscheck", "obligations", "agreements", "bilingual"}},
    "finance": {"home": "/app/finance", "features": {"penalty", "cashflow"}},
    "sales": {"home": "/app/sales", "features": {"terms"}, "redact": True},
    "management": {"home": "/app/management", "features": {"accuracy", "obligations"}},
}

_C = r"/api/contracts/[0-9a-f]{64}"
RESTRICTED: dict[str, list[str]] = {
    "penalty": [_C + r"/penalty$", _C + r"/montecarlo$", r"/api/portfolio/montecarlo$"],
    "cashflow": [_C + r"/cashflow$"],
    "gap": [_C + r"/statute-gap$"],
    "playbook": [_C + r"/playbook$"],
    "crosscheck": [r"/api/crossdoc(/|$)"],
    "obligations": [r"/api/obligations(/|$)", r"/api/alerts(/|$)"],
    "agreements": [r"/api/agreements(/|$)", _C + r"/agreement$"],
    "bilingual": [_C + r"/bilingual-check$", r"/api/bilingual(/|$)"],
    "accuracy": [r"/api/eval(/|$)"],
    "assistant": [_C + r"/chat$"],
    "review": [r"/api/review-queue$", _C + r"/reviews$", _C + r"/golden", r"/api/webhook(/|$)"],
    "buyers": [r"/api/buyers(/|$)"],
}
_RESTRICTED = {f: [re.compile(p) for p in ps] for f, ps in RESTRICTED.items()}

# Values a redacted department never receives (the price and every figure that shows delay exposure).
REDACTED_FIELDS = ("price", "delay_rate", "delay_basis", "delay_cap")


def features(department: str | None) -> set[str] | None:
    """The features a department may use, or None for 'no department' (no restriction beyond the role)."""
    if department is None:
        return None
    return set(POLICY.get(department, {}).get("features", set()))


def home(department: str | None) -> str | None:
    return POLICY.get(department or "", {}).get("home")


def feature_of(path: str) -> str | None:
    for f, pats in _RESTRICTED.items():
        if any(p.search(path) for p in pats):
            return f
    return None


def allows(department: str | None, path: str) -> bool:
    """May this department call this path? Unrestricted (base) routes: yes. A restricted route needs its feature."""
    allowed = features(department)
    if allowed is None:
        return True
    f = feature_of(path)
    return f is None or f in allowed


def redacts(department: str | None) -> bool:
    return bool(POLICY.get(department or "", {}).get("redact"))
