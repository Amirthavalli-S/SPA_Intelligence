import { useQueryClient } from "@tanstack/react-query";
import { Fragment, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { usePacks } from "../api/hooks";
import { apiX } from "../api/trust";
import { GroundingChip } from "../components/GroundingChip";
import { FIELDS, GROUPS, useTermDisplay, type FieldKey } from "../components/termDisplay";
import { Alert } from "../components/ui";
import { WarningsPanel } from "../components/WarningsPanel";
import { useFmt } from "../i18n/format";
import { useMotion } from "../motion/mm";
import { Flip, gsap } from "../motion/registry";
import { ScrambleValue } from "../motion/ScrambleValue";
import { usePrefs } from "../state/prefs";
import { useContractCtx } from "./ctx";

export default function Terms() {
  const { t } = useTranslation();
  const fmt = useFmt();
  const { tier } = usePrefs();
  const { detail, openEvidence } = useContractCtx();
  const qc = useQueryClient();
  const packs = usePacks();
  const display = useTermDisplay();
  const c = detail.contract;
  const warnings = c.warnings ?? [];
  const [sort, setSort] = useState<"field" | "page">("field");
  const flip = useRef<Flip.FlipState | null>(null);
  const root = useRef<HTMLDivElement>(null);

  const rows = useMemo(() => {
    const base = FIELDS.map((k, i) => ({ k, i, item: c[k] }));
    return sort === "page"
      ? [...base].sort((a, b) => (a.item.source_page ?? 999) - (b.item.source_page ?? 999) || a.i - b.i)
      : base;
  }, [c, sort]);

  const toggleSort = () => {
    flip.current = Flip.getState("[data-row]");
    setSort((s) => (s === "field" ? "page" : "field"));
  };
  useLayoutEffect(() => {
    if (flip.current && tier !== "reduced")
      Flip.from(flip.current, { duration: 0.55, ease: "power3.inOut", targets: "[data-row]" });
    flip.current = null;
  }, [sort, tier]);

  useMotion(
    root,
    ({ tier: tr }) => {
      if (tr === "reduced") return;
      gsap.from(gsap.utils.toArray("[data-row]", root.current), {
        y: 14,
        opacity: 0,
        duration: 0.5,
        stagger: 0.04,
        clearProps: "transform,opacity",
      });
    },
    [detail.id],
  );

  const sum = c.payment_plan_percent_sum;
  const bad = sum != null && Math.abs(sum - 100) > 0.01;

  const termRow = (k: FieldKey) => {
    const item = c[k];
    const d = display(k, c);
    const mentioned = d.missing && !!item.source_quote;
    return (
      <tr key={k} data-row data-testid={`row-${k}`} className={d.missing ? "missing-row" : undefined}>
        <th scope="row" className="field" style={{ textAlign: "start" }}>
          {t(`terms.fields.${k}`)}
        </th>
        <td data-label={t("terms.value")} data-testid={`value-${k}`} dir="auto">
          <span className={`val${d.missing ? " missing" : ""}`}>
            <ScrambleValue text={d.text} />
          </span>
          {mentioned && <span className="note">{t("terms.quoteNoValue")}</span>}
        </td>
        <td className="num nowrap" data-label={t("terms.page")}>
          {item.source_page ? (
            <button
              className="chip"
              onClick={() => openEvidence({ field: k, page: item.source_page! })}
              aria-label={t("terms.openAtPage", { page: item.source_page })}
            >
              {fmt.num(item.source_page)}
            </button>
          ) : (
            "–"
          )}
        </td>
        <td data-label={t("terms.quote")} dir="auto">
          {item.source_quote ? (
            <span
              className="quote-cell"
              style={{ display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}
              title={item.source_quote}
            >
              {item.source_quote}
            </span>
          ) : (
            <span style={{ color: "var(--muted)" }}>–</span>
          )}
        </td>
        <td data-label={t("evidence.trust")}>
          <span style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            <GroundingChip item={item} />
            {item.needs_review && !item.human_verified && (
              <Link className="badge warn" to="/app/review">
                {t("evidence.needsReview")}
              </Link>
            )}
          </span>
        </td>
      </tr>
    );
  };

  return (
    <div ref={root} className="data-layer" style={{ display: "grid", gap: "1.2rem" }}>
      <section className="panel" aria-label={t("terms.jurisdiction")}>
        <div className="panel-body" style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center", padding: "0.8rem 1.15rem" }}>
          <label htmlFor="jur" style={{ fontWeight: 700 }}>
            {t("terms.jurisdiction")}
          </label>
          <select
            id="jur"
            value={c.jurisdiction ?? ""}
            onChange={(e) =>
              void apiX
                .setJurisdiction(detail.id, e.target.value || null)
                .then(() => qc.invalidateQueries({ queryKey: ["contract", detail.id] }))
            }
            style={{ minHeight: 44 }}
          >
            <option value="">{t("terms.jurisdictionAuto", { value: c.jurisdiction_detected?.value ?? "ae_dubai" })}</option>
            {packs.data?.packs.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          {c.jurisdiction_detected?.value && (
            <button className="chip" onClick={() => openEvidence({ field: "jurisdiction" })}>
              {t("terms.detectedFrom", { text: c.jurisdiction_detected?.source_quote ?? "" })}
            </button>
          )}
        </div>
      </section>

      <WarningsPanel warnings={warnings} />

      <section className="panel" aria-labelledby="terms-h">
        <div className="panel-head">
          <div style={{ flex: 1, minWidth: 220 }}>
            <h2 id="terms-h" className="display">
              {t("terms.title")}
            </h2>
            <p className="panel-sub">{t("terms.subtitle")}</p>
          </div>
          <button className="chip" onClick={toggleSort} aria-pressed={sort === "page"}>
            {sort === "page" ? t("terms.sortByField") : t("terms.sortByPage")}
          </button>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="rtable dtable" style={{ minWidth: 760 }}>
            <thead>
              <tr>
                <th scope="col" style={{ width: "17%" }}>
                  {t("terms.field")}
                </th>
                <th scope="col" style={{ width: "22%" }}>
                  {t("terms.value")}
                </th>
                <th scope="col" style={{ width: "7%" }}>
                  {t("terms.page")}
                </th>
                <th scope="col" style={{ width: "32%" }}>
                  {t("terms.quote")}
                </th>
                <th scope="col" style={{ width: "22%" }}>
                  {t("evidence.trust")}
                </th>
              </tr>
            </thead>
            <tbody>
              {sort === "page"
                ? rows.map(({ k }) => termRow(k))
                : GROUPS.map((g) => (
                    <Fragment key={g.key}>
                      <tr className="group">
                        <th colSpan={5} scope="colgroup">
                          {t(`terms.groups.${g.key}`)}
                        </th>
                      </tr>
                      {g.fields.map((k) => termRow(k))}
                    </Fragment>
                  ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel" aria-labelledby="plan-h">
        <div className="panel-head">
          <div style={{ flex: 1, minWidth: 220 }}>
            <h2 id="plan-h" className="display">
              {t("terms.plan")}
            </h2>
            <p className="panel-sub">{t("terms.planSub")}</p>
          </div>
          <span className="badge muted">
            {t("terms.milestones")}: <strong className="num">{fmt.num(detail.plan.length)}</strong>
          </span>
          <span data-testid="plan-total" className={`badge ${bad ? "bad" : "ok"}`} style={{ fontSize: "0.9rem" }}>
            {t("terms.planTotal")}: <span className="num">{sum != null ? fmt.pct(sum, sum % 1 ? 2 : 0) : "–"}</span>
          </span>
        </div>
        {sum != null && (
          <div className="panel-body" style={{ paddingBlock: "0.7rem 0.2rem" }}>
            <div className={`meter${bad ? " bad" : ""}`} role="img" aria-label={t("terms.planProgress", { pct: fmt.pct(sum, sum % 1 ? 2 : 0) })}>
              <span style={{ width: `${Math.max(0, Math.min(100, sum))}%` }} />
            </div>
          </div>
        )}
        {bad && sum != null && (
          <div className="panel-body" style={{ paddingBlock: "0.7rem 0.2rem" }}>
            <Alert tone="danger">{t("terms.notTotal100", { total: fmt.pct(sum, 2) })}</Alert>
          </div>
        )}
        <div style={{ overflowX: "auto", marginBlockStart: "0.6rem" }}>
          <table className="rtable dtable" style={{ minWidth: 780 }}>
            <thead>
              <tr>
                {["milestone", "percent", "amount", "due", "trigger", "type", "page"].map((h) => (
                  <th key={h} scope="col">
                    {t(h === "page" ? "terms.page" : `terms.${h}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {detail.plan.map((p, i) => (
                <tr key={i} data-row data-testid="plan-row" className={bad ? "missing-row" : undefined}>
                  <th scope="row" className="field" style={{ textAlign: "start" }} dir="auto">
                    {p.milestone}
                  </th>
                  <td data-label={t("terms.percent")} className="num nowrap">
                    {fmt.pct(p.percent, p.percent % 1 ? 2 : 0)}
                  </td>
                  <td data-label={t("terms.amount")} className="num nowrap" style={{ fontWeight: 600 }}>
                    {fmt.aed(p.amount, 2)}
                  </td>
                  <td data-label={t("terms.due")} className="num nowrap">
                    {p.due_date ? fmt.date(p.due_date) : <span style={{ color: "var(--muted)" }}>–</span>}
                  </td>
                  <td data-label={t("terms.trigger")} style={{ color: "var(--muted)" }} dir="auto">
                    {p.trigger ?? "–"}
                  </td>
                  <td data-label={t("terms.type")}>
                    <span className="badge muted">{t(`terms.types.${p.type}`)}</span>
                  </td>
                  <td data-label={t("terms.page")}>
                    <button
                      className="chip num"
                      title={p.source_quote}
                      aria-label={t("terms.openAtPage", { page: p.source_page })}
                      onClick={() => openEvidence({ field: `payment_plan.${i + 1}`, page: p.source_page })}
                    >
                      {fmt.num(p.source_page)}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
