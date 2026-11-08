import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { apiX, type ReviewItem } from "../api/trust";
import { GroundingChip } from "../components/GroundingChip";
import { Alert, EmptyState, ErrorState, Skeleton } from "../components/ui";
import { useFmt } from "../i18n/format";

/** "price" -> "Purchase price"; "payment_plan.4" -> "Payment plan, row 4". Never show the raw field path to a reader. */
function useFieldLabel() {
  const { t, i18n } = useTranslation();
  return (field: string) => {
    const m = /^(payment_plan|ungrounded_rows|dated_clauses)\.(\d+)$/.exec(field);
    if (m) return t(m[1] === "payment_plan" ? "review.fieldRow" : m[1] === "ungrounded_rows" ? "review.fieldUngrounded" : "review.fieldClause", { n: m[2] });
    return i18n.exists(`terms.fields.${field}`) ? t(`terms.fields.${field}`) : field;
  };
}

function ItemCard({ it }: { it: ReviewItem }) {
  const { t } = useTranslation();
  const label = useFieldLabel();
  const fmt = useFmt();
  const qc = useQueryClient();
  const [val, setVal] = useState("");
  const [note, setNote] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [mode, setMode] = useState<"idle" | "correct">("idle");
  const isRow = /^(payment_plan|ungrounded_rows|dated_clauses)\./.test(it.field);
  const done = () => void qc.invalidateQueries({ queryKey: ["review-queue"] });
  const mut = useMutation({
    mutationFn: (b: { action: "accept" | "correct" | "reject"; value?: unknown }) => apiX.review(it.contract_id, it.field, { ...b, note, reviewer }),
    onSuccess: () => { done(); void qc.invalidateQueries({ queryKey: ["contract", it.contract_id] }); },
  });
  const shown = it.value == null ? null : typeof it.value === "object" ? JSON.stringify(it.value) : typeof it.value === "number" ? fmt.flex(it.value) : String(it.value);
  const correct = () => {
    if (isRow) {
      const n = Number(val);
      mut.mutate({ action: "correct", value: { percent: n } });
    } else mut.mutate({ action: "correct", value: val });
  };
  return (
    <article className="panel" data-testid="review-item" data-field={it.field}>
      <header className="panel-head" style={{ padding: "0.8rem 1.15rem" }}>
        <strong style={{ flex: 1, minWidth: 200, fontSize: "1.05rem" }} dir="auto">
          {label(it.field)}
        </strong>
        <GroundingChip item={{ grounding: { status: it.status }, confidence: it.confidence }} />
        <Link className="chip" to={`/app/contracts/${it.contract_id}/terms`}>{t("review.open")}</Link>
      </header>
      <div className="panel-body" style={{ display: "grid", gap: "1rem" }}>
        <div style={{ display: "grid", gap: "0.9rem", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
          <div style={{ display: "grid", gap: 4, alignContent: "start" }}>
            <span className="group-title" style={{ margin: 0 }}>{t("review.whatRead")}</span>
            <strong style={{ fontSize: "1.25rem" }} className="display" dir="auto">{shown ?? t("review.withheld")}</strong>
            {it.claimed_value && <span style={{ color: "var(--muted)" }}>{t("review.claimed")}: <strong dir="auto">{it.claimed_value}</strong></span>}
          </div>
          <div style={{ display: "grid", gap: 4, alignContent: "start" }}>
            <span className="group-title" style={{ margin: 0 }}>{t("review.quoteHead")}</span>
            {it.source_quote ? (
              <blockquote className="quote-cell" style={{ margin: 0 }} dir="auto">{it.source_quote} {it.source_page ? <span className="num">({t("common.pageShort")} {fmt.num(it.source_page)})</span> : null}</blockquote>
            ) : <span style={{ color: "var(--muted)" }}>–</span>}
            {it.reasons.length > 0 && <small style={{ color: "var(--gold-ink)" }}>{it.reasons.join("; ")}</small>}
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
          <input placeholder={t("review.reviewer")} aria-label={t("review.reviewer")} value={reviewer} onChange={(e) => setReviewer(e.target.value)} style={{ minHeight: 44, width: 150 }} />
          <input placeholder={t("review.note")} aria-label={t("review.note")} value={note} onChange={(e) => setNote(e.target.value)} style={{ minHeight: 44, flex: 1, minWidth: 160 }} />
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
          <button className="btn" disabled={mut.isPending} onClick={() => mut.mutate({ action: "accept" })} data-testid="rv-accept">{t("review.accept")}</button>
          {mode === "idle" ? (
            <button className="btn btn-ghost" onClick={() => setMode("correct")} data-testid="rv-correct">{t("review.correct")}</button>
          ) : (
            <>
              <input aria-label={t("review.newValue")} value={val} onChange={(e) => setVal(e.target.value)} placeholder={isRow ? t("review.percent") : t("review.newValue")} style={{ minHeight: 44, width: 180 }} data-testid="rv-value" />
              <button className="btn" disabled={!val || mut.isPending} onClick={correct} data-testid="rv-save">{t("review.save")}</button>
            </>
          )}
          <button className="btn btn-ghost" disabled={mut.isPending} onClick={() => mut.mutate({ action: "reject" })} data-testid="rv-reject">{t("review.reject")}</button>
        </div>
        <small style={{ color: "var(--muted)" }}>{t("review.acceptHelp")} {t("review.correctHelp")} {t("review.rejectHelp")}</small>
        {mut.error && <Alert tone="danger">{(mut.error as Error).message}</Alert>}
      </div>
    </article>
  );
}

export default function ReviewQueue() {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["review-queue"], queryFn: apiX.reviewQueue });
  const contracts = [...new Map((q.data?.items ?? []).map((i) => [i.contract_id, i.contract_name])).entries()];
  const [exp, setExp] = useState<string | null>(null);
  const ex = useMutation({ mutationFn: (id: string) => apiX.goldenExport(id, true), onSuccess: (d) => setExp(d.path) });
  return (
    <div className="data-layer" style={{ display: "grid", gap: "1rem" }}>
      <section className="panel">
        <div className="panel-head">
          <h1 className="display" style={{ margin: 0, fontSize: "1.5rem", flex: 1 }}>{t("review.title")}</h1>
          <span className={`badge ${q.data && q.data.count > 0 ? "warn" : "ok"}`}>{t("review.count", { count: q.data?.count ?? 0 })}</span>
        </div>
        <div className="panel-body" style={{ display: "grid", gap: 8 }}>
          <p className="page-lead">{t("review.intro")}</p>
          <details style={{ color: "var(--muted)" }}>
            <summary style={{ cursor: "pointer", color: "var(--fg)", fontWeight: 600 }}>{t("review.howTitle")}</summary>
            <p style={{ margin: "0.5rem 0 0" }}>{t("review.how")}</p>
          </details>
        </div>
      </section>
      {q.isLoading && <Skeleton h={200} />}
      {q.error && <ErrorState title={t("errors.generic")} message={(q.error as Error).message} onRetry={() => void q.refetch()} />}
      {q.data && q.data.count === 0 && <EmptyState title={t("review.emptyTitle")} body={t("review.emptyBody")} />}
      {contracts.map(([id, name]) => {
        const items = (q.data?.items ?? []).filter((i) => i.contract_id === id);
        return (
          <section key={id} style={{ display: "grid", gap: 10 }} aria-label={name}>
            <h2 className="display" style={{ margin: "0.4rem 0 0", fontSize: "1.15rem", display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }} dir="auto">
              {name} <span className="badge warn">{t("review.contractCount", { count: items.length })}</span>
            </h2>
            {items.map((it) => <ItemCard key={`${it.contract_id}:${it.field}`} it={it} />)}
          </section>
        );
      })}
      {contracts.length > 0 && (
        <section className="panel panel-body" style={{ display: "grid", gap: 8 }}>
          <strong>{t("review.golden")}</strong>
          <p style={{ margin: 0, color: "var(--muted)" }}>{t("review.goldenHelp")}</p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {contracts.map(([id, name]) => <button key={id} className="btn btn-ghost" onClick={() => ex.mutate(id)}>{name}</button>)}
          </div>
          {exp && <Alert tone="ok">{t("review.exported", { path: exp })}</Alert>}
          {ex.error && <Alert tone="danger">{(ex.error as Error).message}</Alert>}
        </section>
      )}
    </div>
  );
}
