import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { apiX, type AgreementFieldKey, type AgreementResult } from "../api/trust";
import { Alert, EmptyState, ErrorState, Skeleton } from "../components/ui";
import { CurrencyContext, useFmt } from "../i18n/format";

const FIELDS: AgreementFieldKey[] = ["price", "possession_date", "payment_schedule", "penalty_rate", "penalty_cap", "grace_period_days"];

/** One value from the merged result, written for a person. */
function useValue() {
  const { t } = useTranslation();
  const fmt = useFmt();
  return (f: AgreementFieldKey, v: unknown): string => {
    if (v == null) return t("common.notStated");
    switch (f) {
      case "price":
        return fmt.aed(v as number, 0);
      case "possession_date":
        return fmt.date(v as string);
      case "payment_schedule":
        return t("agreements.planRows", { count: (v as unknown[]).length });
      case "penalty_rate": {
        const r = v as { rate: number; basis: string };
        return r.basis === "fixed_per_sqft_per_month"
          ? t("terms.rateFixedMonth", { value: fmt.aed(r.rate, 2) })
          : r.basis === "fixed_per_sqft_per_year"
            ? t("terms.rateFixed", { value: fmt.aed(r.rate, 2) })
            : t("terms.ratePercent", { value: `${fmt.flex(r.rate)}%` });
      }
      case "penalty_cap":
        return t("terms.capValue", { value: `${fmt.flex(v as number)}%` });
      case "grace_period_days":
        return t("terms.daysValue", { value: fmt.num(v as number) });
    }
  };
}

function Detail({ r }: { r: AgreementResult }) {
  const { t } = useTranslation();
  const fmt = useFmt();
  const value = useValue();
  return (
    <div style={{ display: "grid", gap: "1.2rem" }}>
      {r.pending_review > 0 && (
        <Alert tone="warn">
          <span data-testid="agreement-pending">{t("agreements.pending", { count: r.pending_review })}</span>{" "}
          <Link to="/app/review">{t("summary.review.go")}</Link>
        </Alert>
      )}
      {r.problems.map((p) => (
        <Alert key={p} tone="danger">
          {p}
        </Alert>
      ))}

      <section className="panel" aria-labelledby="ag-cur">
        <div className="panel-head">
          <div style={{ flex: 1, minWidth: 220 }}>
            <h2 id="ag-cur" className="display">
              {t("agreements.current")}
            </h2>
            <p className="panel-sub">{t("agreements.currentSub")}</p>
          </div>
          <span className="badge info">{t("agreements.planVersion", { n: r.current.payment_plan_version })}</span>
        </div>
        <div className="panel-body">
          <div className="kpi-grid" data-testid="agreement-current">
            {FIELDS.map((f) => {
              const v = r.current[f];
              const src = r.sources[f];
              return (
                <div key={f} className={`kpi${v == null ? " missing" : ""}`} data-testid={`ag-${f}`}>
                  <span className="label">{t(`agreements.fields.${f}`)}</span>
                  <span className="value" dir="auto">
                    {value(f, v)}
                  </span>
                  <span className="hint">
                    {src ? t("agreements.setBy", { doc: src.name, date: fmt.date(src.date_signed) }) : t("agreements.noDoc")}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="panel" aria-labelledby="ag-tl">
        <div className="panel-head">
          <h2 id="ag-tl" className="display" style={{ flex: 1 }}>
            {t("agreements.timeline")}
          </h2>
        </div>
        <div className="panel-body" style={{ overflowX: "auto" }}>
          <ol className="ag-timeline" data-testid="agreement-timeline">
            {r.timeline.map((e) => (
              <li key={e.doc_id} className="ag-node">
                <span className="ag-dot" aria-hidden="true" />
                <span className="num ag-date">{fmt.date(e.date)}</span>
                <span className="badge muted">{e.doc_type}</span>
                <strong dir="auto">{e.name}</strong>
                {e.changes.length === 0 ? (
                  <span className="hint" style={{ color: "var(--muted)" }}>
                    {t("agreements.noChange")}
                  </span>
                ) : (
                  <ul className="ag-changes">
                    {e.changes.map((c) => (
                      <li key={c.field}>
                        <span style={{ color: "var(--muted)" }}>{t(`agreements.fields.${c.field}`)}: </span>
                        {c.kind === "changed" ? (
                          <>
                            <span style={{ textDecoration: "line-through", color: "var(--muted)" }}>{value(c.field, c.from)}</span> → <strong>{value(c.field, c.to)}</strong>
                          </>
                        ) : (
                          <strong>{value(c.field, c.to)}</strong>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="panel" aria-labelledby="ag-docs">
        <div className="panel-head">
          <h2 id="ag-docs" className="display" style={{ flex: 1 }}>
            {t("agreements.documents")}
          </h2>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="rtable dtable" style={{ minWidth: 520 }}>
            <thead>
              <tr>
                <th scope="col">{t("agreements.doc")}</th>
                <th scope="col">{t("agreements.type")}</th>
                <th scope="col">{t("agreements.signed")}</th>
                <th scope="col">{t("agreements.review")}</th>
              </tr>
            </thead>
            <tbody>
              {r.documents.map((d) => (
                <tr key={d.doc_id}>
                  <th scope="row" className="field" style={{ textAlign: "start" }} dir="auto">
                    <Link to={`/app/contracts/${d.doc_id}/terms`}>{d.name}</Link>
                  </th>
                  <td data-label={t("agreements.type")}>
                    <span className="badge muted">{d.doc_type}</span>
                  </td>
                  <td data-label={t("agreements.signed")} className="num nowrap">
                    {d.date_signed ? fmt.date(d.date_signed) : "–"}
                  </td>
                  <td data-label={t("agreements.review")}>
                    {d.open_reviews ? <span className="badge warn">{t("agreements.open", { count: d.open_reviews })}</span> : <span className="badge ok">✓</span>}
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

export default function Reconciliation() {
  const { t } = useTranslation();
  const { id } = useParams();
  const nav = useNavigate();
  const [text, setText] = useState(id ?? "");
  const list = useQuery({ queryKey: ["agreements"], queryFn: apiX.agreements });
  const one = useQuery({ queryKey: ["agreement", id], queryFn: () => apiX.agreement(id!), enabled: !!id, retry: false });
  const go = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim()) nav(`/app/agreements/${encodeURIComponent(text.trim())}`);
  };
  const missing = one.error instanceof ApiError && one.error.code === "not_found";
  return (
    <div className="data-layer" style={{ display: "grid", gap: "1.2rem" }}>
      <section className="panel">
        <div className="panel-head">
          <h1 className="display" style={{ margin: 0, fontSize: "1.5rem", flex: 1 }}>
            {t("agreements.title")}
          </h1>
        </div>
        <div className="panel-body" style={{ display: "grid", gap: 10 }}>
          <p className="page-lead">{t("agreements.intro")}</p>
          <form onSubmit={go} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <label className="sr-only" htmlFor="ag-search">
              {t("agreements.search")}
            </label>
            <input id="ag-search" value={text} onChange={(e) => setText(e.target.value)} placeholder={t("agreements.search")} style={{ minHeight: 44, flex: 1, minWidth: 220 }} dir="ltr" />
            <button className="btn" type="submit" disabled={!text.trim()}>
              {t("agreements.show")}
            </button>
          </form>
          {list.data && list.data.length > 0 && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }} data-testid="agreement-list">
              {list.data.map((a) => (
                <Link key={a.agreement_id} className="chip" to={`/app/agreements/${encodeURIComponent(a.agreement_id)}`}>
                  {a.agreement_id} · {t("agreements.docCount", { count: a.documents })}
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>
      {!id && list.data && list.data.length === 0 && <EmptyState title={t("agreements.emptyTitle")} body={t("agreements.emptyBody")} />}
      {id && one.isLoading && <Skeleton h={300} />}
      {id && missing && <EmptyState title={t("agreements.notFoundTitle")} body={t("agreements.notFoundBody", { id })} />}
      {id && one.error && !missing && <ErrorState title={t("errors.generic")} message={(one.error as Error).message} onRetry={() => void one.refetch()} />}
      {one.data && (
        <CurrencyContext.Provider value={one.data.currency}>
          <Detail r={one.data} />
        </CurrencyContext.Provider>
      )}
    </div>
  );
}
