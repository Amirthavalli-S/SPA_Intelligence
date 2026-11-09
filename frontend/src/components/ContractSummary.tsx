import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import type { ContractData } from "../api/client";
import { useFmt } from "../i18n/format";
import { countOpenReviews, useTermDisplay, type FieldKey } from "./termDisplay";

const CARDS: FieldKey[] = ["buyer", "unit_id", "price", "area_sqft", "handover_date"];

/** The few things a reader wants first, as cards: who, what, how much, when, whether the payment plan adds up, and whether a person still has to check anything. */
export function ContractSummary({ c, restricted }: { c: ContractData; restricted?: string[] | null }) {
  const { t } = useTranslation();
  const fmt = useFmt();
  const display = useTermDisplay();
  const open = countOpenReviews(c);
  const sum = c.payment_plan_percent_sum;
  const planBad = sum != null && Math.abs(sum - 100) > 0.01;
  return (
    <section aria-labelledby="glance-h">
      <h2 id="glance-h" className="sr-only">
        {t("summary.title")}
      </h2>
      <div className="kpi-grid" data-testid="summary">
        {CARDS.map((k) => {
          const d = display(k, c, restricted);
          const item = c[k];
          const hint = d.missing && item.source_quote ? t("summary.contractSays", { text: item.source_quote }) : null;
          return (
            <div key={k} className={`kpi${d.missing || d.restricted ? " missing" : ""}`} data-testid={`kpi-${k}`}>
              <span className="label">{t(`terms.fields.${k}`)}</span>
              <span className="value" dir="auto">
                {d.text}
              </span>
              {hint && <span className="hint">{hint}</span>}
            </div>
          );
        })}
      </div>
      <div className="kpi-grid wide">
        <div className="kpi" data-testid="kpi-plan">
          <span className="label">{t("summary.planTotal")}</span>
          <span className="value num">{sum != null ? fmt.pct(sum, sum % 1 ? 2 : 0) : "–"}</span>
          {sum != null && (
            <>
              <span className="hint">{t(planBad ? "summary.planBad" : "summary.planOk")}</span>
              <div className={`meter${planBad ? " bad" : ""}`} aria-hidden="true">
                <span style={{ width: `${Math.max(0, Math.min(100, sum))}%` }} />
              </div>
            </>
          )}
        </div>
        <div className="kpi" data-testid="summary-review">
          <span className="label">{t("summary.review.title")}</span>
          <span className="value" style={{ color: open ? "var(--gold-ink)" : "var(--ok)" }}>
            {open ? t("summary.review.open", { count: open }) : t("summary.review.done")}
          </span>
          {open > 0 ? (
            <Link to="/app/review" className="btn" style={{ justifySelf: "start", marginBlockStart: 6, padding: "0.4rem 1rem", fontSize: "0.9rem" }}>
              {t("summary.review.go")}
            </Link>
          ) : (
            <span className="hint">{t("summary.review.help")}</span>
          )}
        </div>
      </div>
    </section>
  );
}
