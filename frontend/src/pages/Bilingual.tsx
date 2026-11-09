import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "../api/client";
import { useContracts } from "../api/hooks";
import { apiX, type BilingualPair } from "../api/trust";
import { Alert, EmptyState, Skeleton } from "../components/ui";

/** Arabic vs English version of one contract. Figures are compared by the server in plain code; this page only shows the result. */
export default function Bilingual() {
  const { t } = useTranslation();
  const list = useContracts();
  const [cid, setCid] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const run = useMutation({ mutationFn: (arabic: File | null) => apiX.bilingual(cid || list.data?.[0]?.id || "", arabic) });
  const r = run.data;
  const ready = !!(cid || list.data?.length);
  if (list.isLoading) return <Skeleton h={240} />;
  return (
    <div className="data-layer" style={{ display: "grid", gap: "1.2rem" }} data-testid="bilingual-page">
      <section className="panel">
        <h1 className="display" style={{ margin: 0, fontSize: "1.6rem" }}>
          {t("bilingual.title")}
        </h1>
        <p style={{ color: "var(--muted)", lineHeight: 1.6 }}>{t("bilingual.intro")}</p>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
          <label style={{ display: "grid", gap: 4 }}>
            <span>{t("bilingual.contract")}</span>
            <select value={cid} onChange={(e) => setCid(e.target.value)} data-testid="bi-contract">
              {(list.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: "grid", gap: 4 }}>
            <span>{t("bilingual.file")}</span>
            <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} data-testid="bi-file" />
          </label>
          <button className="btn" disabled={!ready || !file || run.isPending} onClick={() => run.mutate(file)} data-testid="bi-run">
            {run.isPending ? t("bilingual.running") : t("bilingual.run")}
          </button>
          <button className="chip" disabled={!ready || run.isPending} onClick={() => run.mutate(null)} data-testid="bi-sample">
            {t("bilingual.sample")}
          </button>
        </div>
        <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>{t("bilingual.note")}</p>
      </section>
      {run.error && <Alert tone="danger">{(run.error as ApiError).message}</Alert>}
      {!r && !run.error && <EmptyState title={t("bilingual.title")} body={t("bilingual.empty")} />}
      {r && (
        <section className="panel" aria-live="polite">
          <p className="display" style={{ fontSize: "1.2rem", fontWeight: 700 }} data-testid="bi-summary">
            {t("bilingual.summary", r.summary)}
          </p>
          <div style={{ display: "grid", gap: 10 }}>
            {r.pairs.map((p: BilingualPair, i) => (
              <article key={i} className="card" style={{ padding: "0.8rem 1rem" }} data-testid={`bi-${p.status}`}>
                <strong>{p.clause_id ? t("bilingual.clause", { id: p.clause_id }) : t("bilingual.noId")}</strong>{" "}
                <span className={`badge ${p.status === "mismatch" ? "badge-danger" : ""}`}>{t(`bilingual.status.${p.status}`)}</span>
                {p.aligned_by === "figures" && <div style={{ color: "var(--gold-ink)" }}>{t("bilingual.pairedByFigures")}</div>}
                {p.differences.map((d) => (
                  <div key={d} style={{ color: "var(--danger)", fontWeight: 600 }}>
                    {d}
                  </div>
                ))}
                <div style={{ display: "grid", gap: 6, gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", marginBlockStart: 6 }}>
                  <div lang="en" dir="ltr">
                    <small style={{ color: "var(--muted)" }}>
                      {t("bilingual.english")}
                      {p.page_en ? ` · ${t("bilingual.page", { n: p.page_en })}` : ""}
                    </small>
                    <div>{p.english_text ?? "–"}</div>
                  </div>
                  <div lang="ar" dir="rtl">
                    <small style={{ color: "var(--muted)" }}>
                      {t("bilingual.arabic")}
                      {p.page_ar ? ` · ${t("bilingual.page", { n: p.page_ar })}` : ""}
                    </small>
                    <div>{p.arabic_text ?? "–"}</div>
                  </div>
                </div>
              </article>
            ))}
          </div>
          <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>{r.disclaimer}</p>
        </section>
      )}
    </div>
  );
}
