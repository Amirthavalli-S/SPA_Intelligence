import { useTranslation } from "react-i18next";
import { Link, Navigate } from "react-router-dom";
import { homeRouteFor, isDepartment, kindOf, type Department } from "../auth/roles";
import { useAuth } from "../auth/useAuth";
import { Skeleton } from "../components/ui";

/** Where each feature lives. Contract pages (null) are opened from the contract list; the others have their own page. */
const WHERE: Record<string, string | null> = {
  terms: null,
  gap: null,
  penalty: null,
  cashflow: null,
  playbook: null,
  obligations: "/app/watch",
  crosscheck: "/app/crosscheck",
  agreements: "/app/agreements",
  accuracy: "/app/accuracy",
  bilingual: "/app/bilingual",
};
const ORDER = ["terms", "gap", "playbook", "crosscheck", "agreements", "bilingual", "penalty", "cashflow", "obligations", "accuracy"];

/** A department's own start page: what the team does here, and only the tools that team has. */
export default function DepartmentHome({ dept }: { dept: Department }) {
  const { t } = useTranslation();
  const me = useAuth();
  const kind = kindOf(me.data);
  if (me.isLoading) return <Skeleton h={240} />; // never show an empty list while we do not yet know whose home this is
  // Only the signed-in department sees its own home. Anyone else is sent to where they belong; there is no way to browse another team's page.
  if (me.data && (kind !== "staff" || me.data.department !== dept)) {
    return <Navigate to={isDepartment(me.data.department) && kind === "staff" ? homeRouteFor(kind, me.data.department) : "/app"} replace />;
  }
  const features = (me.data?.features ?? []).filter((f) => f in WHERE);
  const tools = ORDER.filter((f) => features.includes(f));
  return (
    <div className="data-layer" style={{ display: "grid", gap: "1.2rem" }} data-testid={`dept-home-${dept}`}>
      <section className="panel">
        <div className="panel-head">
          <h1 className="display" style={{ margin: 0, fontSize: "1.6rem", flex: 1 }}>
            {t(`dept.${dept}.title`)}
          </h1>
          <span className="badge info">{t(`dept.${dept}.name`)}</span>
        </div>
        <div className="panel-body" style={{ display: "grid", gap: 8 }}>
          <p className="page-lead">{t(`dept.${dept}.intro`)}</p>
        </div>
      </section>
      <section aria-labelledby="dept-tools" style={{ display: "grid", gap: "0.8rem" }}>
        <h2 id="dept-tools" className="display" style={{ margin: 0, fontSize: "1.25rem" }}>
          {t("dept.tools")}
        </h2>
        <ul className="steps" style={{ listStyle: "none", margin: 0, padding: 0 }} data-testid="dept-tools">
          {tools.map((f) => {
            const to = WHERE[f];
            return (
              <li key={f} className="step" data-testid={`tool-${f}`}>
                <strong>{t(`dept.features.${f}.title`)}</strong>
                <span>{t(`dept.features.${f}.body`)}</span>
                {to ? (
                  <Link to={to} className="btn" style={{ justifySelf: "start", marginBlockStart: 6, padding: "0.4rem 1rem", fontSize: "0.9rem" }}>
                    {t("dept.open")}
                  </Link>
                ) : (
                  <small style={{ color: "var(--muted)" }}>{t("dept.fromList")}</small>
                )}
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
