"""Do the English and the Arabic version of ONE contract say the same thing, clause by clause?

Not the app's interface translation: this compares two versions of a CONTRACT, where a translation slip or an unsynchronised
update can change a date, a period, a percentage or an amount, and typically only one language version is binding.

Plain code does the deciding, as everywhere else in this app: each version is cut into numbered clauses, clauses are paired by number,
and the FIGURES in each pair (amounts, percentages, periods, years, dates) are compared. A model is optional and only asked a narrow
question about a pair whose figures agree, to catch a wording difference that carries no figure (see `judge`).

Arabic in PDFs is often stored in VISUAL order (letters and digits reversed). That is detected from the shaped-letter characters
and the digits are turned back before comparing. Pairing is by clause number; if numbering does not line up, pairs are matched by the
figures they share, which is weaker and is reported as such. Limits: pairing needs numbered clauses; a combined bilingual PDF
(both languages on the same page) has to be split first; wording is NOT compared unless a model is used.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Optional

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٪٫٬", "01234567890123456789%.,")
_ARABIC = re.compile(r"[؀-ۿﭐ-﷿ﹰ-ﻼ]")
_PRESENTATION = re.compile(r"[ﭐ-﷿ﹰ-ﻼ]")          # shaped letters: only visual-order text has them
_DIGIT_RUN = re.compile(r"[0-9]+(?:[.,][0-9]+)*")
_START = re.compile(r"^\s*(\d{1,3})\s*[.)\-:]\s*(.*)$")                  # "3. text"
_END_AR = re.compile(r"^(.*?)\s*[.)\-:]\s*(\d{1,3})\s*$")               # visual-order Arabic: the number ends the first line ("text .3")


@dataclass
class Clause:
    id: Optional[str]
    text: str
    page: int
    page_end: int
    visual: bool = False
    lines: list[str] = field(default_factory=list, repr=False)


def is_visual(text: str) -> bool:
    return bool(_PRESENTATION.search(text))


def normalize(text: str, reverse_digits: bool = False) -> str:
    """NFKC (shaped letters -> base letters), Arabic-Indic digits -> 0-9. With `reverse_digits`, each digit run is turned back (some
    extractors keep digit runs in their visual, reversed order; `check` decides that per document by comparing with the English figures)."""
    t = unicodedata.normalize("NFKC", text).translate(_AR_DIGITS)
    if reverse_digits:
        t = _DIGIT_RUN.sub(lambda m: m.group(0)[::-1], t)
    return t


def _lines(pages: list[str]):
    for pg, text in enumerate(pages, 1):
        for ln in text.splitlines():
            if ln.strip():
                yield pg, ln.strip()


def _fix(text: str, reverse_digits: bool) -> str:
    return _DIGIT_RUN.sub(lambda m: m.group(0)[::-1], text) if reverse_digits else text


def _join_numbers(lines):
    """Extractors often put the clause number on a line of its own ("1" then ". text"): join them."""
    out, i = [], list(lines)
    k = 0
    while k < len(i):
        pg, ln = i[k]
        if re.fullmatch(r"\d{1,3}", ln) and k + 1 < len(i) and re.match(r"^[.)\-:]", i[k + 1][1]):
            out.append((i[k + 1][0], ln + i[k + 1][1])); k += 2
        else:
            out.append((pg, ln)); k += 1
    return out


def segment(pages: list[str], reverse_digits: bool = False) -> list[Clause]:
    """Numbered clauses in reading order. A numbered line starts a clause; every other line continues the current one. With no numbering at
    all, each page is one clause (id None), so the check still runs and says it paired by page."""
    clauses: list[Clause] = []
    cur: Optional[Clause] = None
    doc_visual = any(is_visual(p) for p in pages)          # shaped letters: the text is stored in visual order (number ends the line)
    for pg, raw in _join_numbers(_lines(pages)):
        visual = doc_visual
        line = normalize(raw)
        num, body = None, line
        m = _START.match(line)
        if m:
            num, body = m.group(1), m.group(2)
        elif _ARABIC.search(raw):
            m = _END_AR.match(line)
            if m:
                num, body = m.group(2), m.group(1)
        if num is not None:
            body = _fix(body, reverse_digits)
            cur = Clause(str(int(num)), body, pg, pg, visual, [body])
            clauses.append(cur)
        elif cur is not None:
            line = _fix(line, reverse_digits)
            cur.lines.append(line); cur.text += " " + line; cur.page_end = pg; cur.visual = cur.visual or visual
    if not clauses:
        for pg, text in enumerate(pages, 1):
            body = " ".join(normalize(x, reverse_digits).strip() for x in text.splitlines() if x.strip())
            if body:
                clauses.append(Clause(None, body, pg, pg, is_visual(text)))
    return clauses


_NUM = re.compile(r"(\d+(?:[.,]\d+)*)\s*(%)?")


def figures(text: str) -> Counter:
    """The figures a clause states: amounts, percentages, periods, years, days of a date. 1,00,000 and 100000 are the same figure."""
    out: Counter = Counter()
    for m in _NUM.finditer(text):
        raw = m.group(1).replace(",", "")
        try:
            v = float(raw)
        except ValueError:
            continue
        out[f"{v:g}{'%' if m.group(2) else ''}"] += 1
    return out


def _pair_status(en: Clause, ar: Clause) -> dict:
    fe, fa = figures(en.text), figures(ar.text)
    diffs = []
    only_en, only_ar = fe - fa, fa - fe
    if only_en or only_ar:
        diffs.append("English states " + (", ".join(sorted(only_en.elements())) or "no extra figure")
                     + "; Arabic states " + (", ".join(sorted(only_ar.elements())) or "no extra figure"))
    return {"status": "mismatch" if diffs else "match", "differences": diffs, "compared": sum(fe.values()) + sum(fa.values()),
            "checked_by": ["figures"]}


def _row(en: Optional[Clause], ar: Optional[Clause], aligned_by: str, status: dict) -> dict:
    return {"clause_id": (en or ar).id, "english_text": en.text if en else None, "arabic_text": ar.text if ar else None,
            "page_en": en.page if en else None, "page_ar": ar.page if ar else None, "aligned_by": aligned_by, **status}


def check(en_pages: list[str], ar_pages: list[str], judge: Optional[Callable[[str, str], dict]] = None, max_judged: int = 40) -> dict:
    """Pair the clauses of the two versions and compare them. `judge(english, arabic) -> {"same": bool, "difference": str}` is optional,
    and is asked only about pairs whose figures agree."""
    en = segment(en_pages)
    ef = Counter()
    for c in en:
        ef += figures(c.text)
    # digit runs in visual-order Arabic may be reversed ("2028" stored as "8202"): keep the orientation that agrees more with English
    ar_f, ar_r = segment(ar_pages), segment(ar_pages, True)
    def agree(cl):
        t = Counter()
        for c in cl:
            t += figures(c.text)
        return sum((t & ef).values())
    ar = ar_r if agree(ar_r) > agree(ar_f) else ar_f
    by_ar = {c.id: c for c in ar if c.id is not None}
    pairs, used = [], set()
    for c in en:
        a = by_ar.get(c.id) if c.id is not None else None
        if a is not None and id(a) not in used:
            used.add(id(a))
            pairs.append(_row(c, a, "number", _pair_status(c, a)))
        else:
            pairs.append(_row(c, None, "none", {"status": "unaligned", "differences": [], "compared": 0, "checked_by": []}))
    # weaker fallback: an English clause with no numbered partner is paired with an unused Arabic clause that shares its figures
    for i, p in enumerate(pairs):
        if p["status"] != "unaligned":
            continue
        fe = figures(p["english_text"])
        if not fe:
            continue
        best = max(((sum((fe & figures(a.text)).values()) / max(1, sum((fe | figures(a.text)).values())), a) for a in ar if id(a) not in used),
                   key=lambda x: x[0], default=(0, None))
        if best[1] is not None and best[0] >= 0.6:
            used.add(id(best[1]))
            en_c = next(c for c in en if c.text == p["english_text"] and c.page == p["page_en"])
            pairs[i] = _row(en_c, best[1], "figures", _pair_status(en_c, best[1]))
    for a in ar:
        if id(a) not in used:
            pairs.append(_row(None, a, "none", {"status": "unaligned", "differences": [], "compared": 0, "checked_by": []}))
    calls = 0
    if judge is not None:
        for p in pairs:
            if p["status"] == "match" and p["english_text"] and p["arabic_text"] and calls < max_judged:
                calls += 1
                r = judge(p["english_text"], p["arabic_text"])
                p["checked_by"].append("model")
                if not r.get("same", True):
                    p["status"] = "mismatch"
                    p["differences"].append("Wording: " + str(r.get("difference") or "the two versions differ")[:300])
    c = Counter(p["status"] for p in pairs)
    return {"pairs": pairs, "summary": {"match": c["match"], "mismatch": c["mismatch"], "unaligned": c["unaligned"], "total": len(pairs)},
            "paired_by_number": sum(1 for p in pairs if p["aligned_by"] == "number"), "model_calls": calls,
            "english_clauses": len(en), "arabic_clauses": len(ar)}
