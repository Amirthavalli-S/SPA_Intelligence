import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useContracts, useEvalResults, useHealth } from "../api/hooks";
import { apiX } from "../api/trust";
import { useFmt } from "../i18n/format";

const TEAMS = ["legal", "finance", "sales", "management", "buyers"] as const;
const CAPS = ["extraction", "penalty", "cashflow", "crosscheck", "playbook", "reconcile", "buyer", "review"] as const;
const CONTROLS = ["packs", "evidence", "audit", "rls", "roles", "human"] as const;

function Stat({ label, value, note, testid }: { label: string; value: string | null; note?: string; testid: string }) {
  const { t } = useTranslation();
  return (
    <div className={`kpi${value == null ? " missing" : ""}`} data-testid={testid}>
      <span className="label">{label}</span>
      <span className="value num">{value ?? "–"}</span>
      <span className="hint">{value == null ? t("enterprise.unavailable") : note}</span>
    </div>
  );
}

/**
 * A sober, business-first page next to the cinematic front page. Every figure is read live from this server; if a figure cannot be
 * read (no results yet, or this account may not see it) the tile says so, and nothing is ever filled in with a typed-in number.
 */
export default function Enterprise() {
  const { t } = useTranslation();
  const fmt = useFmt();
  const ev = useEvalResults();
  const list = useContracts();
  const health = useHealth();
  const ag = useQuery({ queryKey: ["agreements"], queryFn: apiX.agreements, retry: false });

  const o = ev.data?.overall;
  const pct = (v: number) => fmt.pct(v * 100, v >= 0.9995 ? 0 : 1);
  const contracts = list.data;
  const extracted = contracts?.filter((c) => c.status === "extracted");
  const flagged = extracted?.filter((c) => c.warnings_count > 0);
  const warnings = extracted?.reduce((n, c) => n + c.warnings_count, 0);
  const db = health.data?.database as { enabled?: boolean; ok?: boolean; rls_on?: boolean; tables?: string[] } | undefined;

  return (
    <div style={{ display: "grid", gap: "2.2rem", maxWidth: 1180, margin: "0 auto", padding: "5.6rem 1.2rem 2rem" }} data-testid="enterprise">
      <header style={{ display: "grid", gap: "0.9rem", maxWidth: 820 }}>
        <span className="badge info" style={{ justifySelf: "start" }}>{t("enterprise.eyebrow")}</span>
        <h1 className="display" style={{ margin: 0, fontSize: "clamp(2rem,4.6vw,3.2rem)", lineHeight: 1.1 }}>{t("enterprise.title")}</h1>
        <p className="page-lead" style={{ fontSize: "1.1rem" }}>{t("enterprise.lead")}</p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <Link className="btn" to="/app">{t("enterprise.open")}</Link>
          <Link className="btn btn-ghost" to="/">{t("enterprise.story")}</Link>
        </div>
      </header>

      <section aria-labelledby="ent-problem" style={{ display: "grid", gap: "0.8rem" }}>
        <h2 id="ent-problem" className="display" style={{ margin: 0, fontSize: "1.5rem" }}>{t("enterprise.problemTitle")}</h2>
        <p className="page-lead">{t("enterprise.problemLead")}</p>
        <div className="kpi-grid" data-testid="problem-strip">
          <Stat testid="stat-contracts" label={t("enterprise.stat.contracts")} value={extracted ? fmt.num(extracted.length) : null} note={t("enterprise.stat.contractsNote", { total: fmt.num(contracts?.length ?? 0) })} />
          <Stat testid="stat-flagged" label={t("enterprise.stat.flagged")} value={extracted && extracted.length ? `${fmt.num(flagged?.length ?? 0)} / ${fmt.num(extracted.length)}` : null} note={t("enterprise.stat.flaggedNote")} />
          <Stat testid="stat-warnings" label={t("enterprise.stat.warnings")} value={warnings != null && extracted?.length ? fmt.num(warnings) : null} note={t("enterprise.stat.warningsNote")} />
        </div>
      </section>

      <section aria-labelledby="ent-proof" style={{ display: "grid", gap: "0.8rem" }}>
        <h2 id="ent-proof" className="display" style={{ margin: 0, fontSize: "1.5rem" }}>{t("enterprise.proofTitle")}</h2>
        <div className="kpi-grid" data-testid="proof-strip">
          <Stat testid="stat-accuracy" label={t("enterprise.stat.accuracy")} value={o?.value_accuracy != null ? pct(o.value_accuracy) : null}
            note={o && ev.data ? t("enterprise.stat.accuracyNote", { checks: fmt.num(o.checks), files: fmt.num(ev.data.files.length), date: fmt.date(ev.data.generated_at.slice(0, 10)) }) : undefined} />
          <Stat testid="stat-quotes" label={t("enterprise.stat.quotes")} value={o?.quote_accuracy != null ? pct(o.quote_accuracy) : null}
            note={o ? t("enterprise.stat.quotesNote", { n: fmt.num(o.quotes_checked) }) : undefined} />
          <Stat testid="stat-agreements" label={t("enterprise.stat.agreements")} value={ag.data ? fmt.num(ag.data.length) : null} note={t("enterprise.stat.agreementsNote")} />
          <Stat testid="stat-rls" label={t("enterprise.stat.rls")} value={db?.enabled && db.ok ? (db.rls_on ? t("enterprise.on") : t("enterprise.off")) : null}
            note={db?.tables ? t("enterprise.stat.rlsNote", { n: fmt.num(db.tables.length) }) : undefined} />
        </div>
        <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.88rem" }}>{t("enterprise.proofFoot")}</p>
      </section>

      <section aria-labelledby="ent-teams" style={{ display: "grid", gap: "0.8rem" }}>
        <h2 id="ent-teams" className="display" style={{ margin: 0, fontSize: "1.5rem" }}>{t("enterprise.teamsTitle")}</h2>
        <ul className="steps" style={{ listStyle: "none", margin: 0, padding: 0 }} data-testid="teams">
          {TEAMS.map((k) => (
            <li key={k} className="step" data-testid={`team-${k}`}>
              <strong>{t(`enterprise.teams.${k}.name`)}</strong>
              <span>{t(`enterprise.teams.${k}.body`)}</span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="ent-caps" style={{ display: "grid", gap: "0.8rem" }}>
        <h2 id="ent-caps" className="display" style={{ margin: 0, fontSize: "1.5rem" }}>{t("enterprise.capsTitle")}</h2>
        <ul className="steps" style={{ listStyle: "none", margin: 0, padding: 0, gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }} data-testid="capabilities">
          {CAPS.map((k) => (
            <li key={k} className="panel" data-testid={`cap-${k}`} style={{ padding: "1rem 1.1rem", display: "grid", gap: 8, alignContent: "start" }}>
              <strong className="display" style={{ fontSize: "1.15rem" }}>{t(`enterprise.caps.${k}.name`)}</strong>
              <span style={{ color: "var(--muted)" }}>{t(`enterprise.caps.${k}.body`)}</span>
              <span style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {(["a", "b", "c"] as const).map((b) => (
                  <span key={b} className="badge ok">✓ {t(`enterprise.caps.${k}.proof.${b}`)}</span>
                ))}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="ent-ctl" className="panel" style={{ padding: "1.2rem 1.3rem", display: "grid", gap: "0.8rem" }} data-testid="controls">
        <h2 id="ent-ctl" className="display" style={{ margin: 0, fontSize: "1.5rem" }}>{t("enterprise.controlsTitle")}</h2>
        <p className="page-lead">{t("enterprise.controlsLead")}</p>
        <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
          {CONTROLS.map((k) => (
            <li key={k} style={{ display: "grid", gap: 2 }}>
              <strong>{t(`enterprise.controls.${k}.name`)}</strong>
              <span style={{ color: "var(--muted)", fontSize: "0.93rem" }}>{t(`enterprise.controls.${k}.body`)}</span>
            </li>
          ))}
        </ul>
        <small style={{ color: "var(--muted)" }}>{t("enterprise.controlsFoot")}</small>
      </section>
    </div>
  );
}
