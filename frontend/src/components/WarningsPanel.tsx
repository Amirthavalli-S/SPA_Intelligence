import { useTranslation } from "react-i18next";
import { Alert, WarningCard } from "./ui";

/** Messages the extraction produced that only say something is not in the contract: informational, not a problem to fix. */
const isNote = (w: string) => /is not stated in the contract|^No cancellation clause|no cancellation clause found/i.test(w);

/** All warnings for a contract in one panel: what needs a person first, then what is only for information. */
export function WarningsPanel({ warnings }: { warnings: string[] }) {
  const { t } = useTranslation();
  if (!warnings.length) return <Alert tone="ok">{t("terms.noWarnings")}</Alert>;
  const action = warnings.filter((w) => !isNote(w));
  const notes = warnings.filter(isNote);
  return (
    <section className="panel" aria-label={t("terms.warnings")} data-testid="warnings-panel">
      <div className="panel-head">
        <div style={{ flex: 1, minWidth: 220 }}>
          <h2 className="display">{t("terms.warnTitle")}</h2>
          <p className="panel-sub">{t("terms.warnSub")}</p>
        </div>
        {action.length > 0 && <span className="badge bad">{t("terms.warnAction", { count: action.length })}</span>}
        {notes.length > 0 && <span className="badge info">{t("terms.warnNotes", { count: notes.length })}</span>}
      </div>
      <div className="panel-body" style={{ display: "grid", gap: 8 }}>
        {action.length > 0 && <h3 className="group-title">{t("terms.attention")}</h3>}
        {action.map((w) => (
          <WarningCard key={w}>{w}</WarningCard>
        ))}
        {notes.length > 0 && <h3 className="group-title">{t("terms.notesTitle")}</h3>}
        {notes.map((w) => (
          <WarningCard key={w} tone="note">
            {w}
          </WarningCard>
        ))}
      </div>
    </section>
  );
}
