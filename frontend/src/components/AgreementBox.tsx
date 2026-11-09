import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { apiX } from "../api/trust";
import { Alert } from "./ui";

const TYPES = ["SPA", "Addendum", "Extension Letter", "RERA Filing", "Brochure", "CRM Export"];

/** Which agreement this document belongs to, what kind of document it is and when it was signed. Saved by a reviewer; the server refuses anyone else. */
export function AgreementBox({ contractId, agreementId, docType, dateSigned }: { contractId: string; agreementId?: string | null; docType?: string | null; dateSigned?: string | null }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [aid, setAid] = useState(agreementId ?? "");
  const [type, setType] = useState(docType ?? "SPA");
  const [signed, setSigned] = useState(dateSigned ?? "");
  const save = useMutation({
    mutationFn: (clear: boolean) =>
      apiX.setAgreement(contractId, clear ? { agreement_id: null, doc_type: null, date_signed: null } : { agreement_id: aid.trim() || null, doc_type: aid.trim() ? type : null, date_signed: signed || null }),
    onSuccess: (_d, clear) => {
      if (clear) {
        setAid("");
        setSigned("");
      }
      void qc.invalidateQueries({ queryKey: ["contracts"] });
      void qc.invalidateQueries({ queryKey: ["agreements"] });
      void qc.invalidateQueries({ queryKey: ["agreement"] });
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate(false);
  };
  return (
    <details style={{ color: "var(--muted)" }} data-testid="agreement-box">
      <summary style={{ cursor: "pointer", color: "var(--fg)", fontWeight: 600 }}>
        {t("agreements.link")}
        {agreementId && (
          <>
            {": "}
            <Link to={`/app/agreements/${encodeURIComponent(agreementId)}`} data-testid="agreement-link" onClick={(e) => e.stopPropagation()}>
              {agreementId}
            </Link>{" "}
            {docType && <span className="badge muted">{docType}</span>}
          </>
        )}
      </summary>
      <form onSubmit={submit} style={{ display: "grid", gap: 10, paddingBlockStart: 8, maxWidth: 560 }}>
        <p style={{ margin: 0 }}>{t("agreements.linkHelp")}</p>
        <label style={{ display: "grid", gap: 4 }}>
          <span>{t("agreements.id")}</span>
          <input value={aid} onChange={(e) => setAid(e.target.value)} dir="ltr" maxLength={40} style={{ minHeight: 44 }} />
        </label>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <label style={{ display: "grid", gap: 4, flex: 1, minWidth: 180 }}>
            <span>{t("agreements.docType")}</span>
            <select value={type} onChange={(e) => setType(e.target.value)} style={{ minHeight: 44 }}>
              {TYPES.map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </label>
          <label style={{ display: "grid", gap: 4, flex: 1, minWidth: 180 }}>
            <span>{t("agreements.dateSigned")}</span>
            <input type="date" value={signed} onChange={(e) => setSigned(e.target.value)} dir="ltr" style={{ minHeight: 44 }} />
          </label>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button className="btn" type="submit" disabled={save.isPending}>
            {t("agreements.save")}
          </button>
          {agreementId && (
            <button className="btn btn-ghost" type="button" disabled={save.isPending} onClick={() => save.mutate(true)}>
              {t("agreements.clear")}
            </button>
          )}
        </div>
        {save.isSuccess && <Alert tone="ok">{t("agreements.saved")}</Alert>}
        {save.error && <Alert tone="danger">{(save.error as Error).message}</Alert>}
      </form>
    </details>
  );
}
