import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useSearchParams } from "react-router-dom";
import { request } from "../api/client";
import { EmailSignIn } from "../auth/EmailSignIn";
import { needsSignIn, safeNext, useAuth } from "../auth/useAuth";
import { Skeleton } from "../components/ui";
import { useMotion } from "../motion/mm";
import { gsap } from "../motion/registry";
import { Dunes } from "../scenes/Dunes";
import { MashrabiyaBand } from "../scenes/Mashrabiya";
import { Skyline } from "../scenes/Skyline";
import { Stars } from "../scenes/Stars";

const ERRORS = ["state", "failed", "cancelled", "not_allowed"];

function GitHubMark() {
  return (
    <svg width="22" height="22" viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38v-1.33c-2.23.48-2.7-1.07-2.7-1.07-.36-.92-.89-1.17-.89-1.17-.73-.5.06-.49.06-.49.8.06 1.23.83 1.23.83.72 1.22 1.88.87 2.34.66.07-.52.28-.87.5-1.07-1.78-.2-3.65-.89-3.65-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.28.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48v2.2c0 .21.15.46.55.38A8 8 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  );
}

const Icon = ({ children }: { children: ReactNode }) => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
);
const POINTS = [
  { key: "cite", icon: <Icon><path d="M7 3h8l4 4v14H7z" /><path d="M15 3v4h4" /><path d="M10 12h6M10 16h6" /></Icon> },
  { key: "calc", icon: <Icon><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M8 7h8M8 12h2M12 12h2M16 12h0M8 16h2M12 16h2M16 16h0" /></Icon> },
  { key: "human", icon: <Icon><circle cx="12" cy="8" r="3.5" /><path d="M5 20c1-4 4-6 7-6s6 2 7 6" /><path d="m16 5 1.5 1.5L20 4" /></Icon> },
];

/** The first page a visitor sees when sign-in is required: a short promise and a quote beside the sign-in card, in the UAE dusk scene. */
export default function Login() {
  const { t, i18n } = useTranslation();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const err = params.get("error");
  const me = useAuth();
  const cfg = useQuery({ queryKey: ["auth-config"], queryFn: () => request<{ mode: string; github: boolean; email?: boolean }>("/auth/config"), retry: false });
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.documentElement.dataset.scene = "dark"; // dark cinematic page in both themes, like the landing page
    return () => void delete document.documentElement.dataset.scene;
  }, []);
  useMotion(root, ({ tier }) => {
    if (tier === "reduced" || !root.current) return;
    const q = gsap.utils.selector(root.current);
    gsap.from(q(".login-card"), { y: 24, opacity: 0, duration: 0.7, ease: "power3.out", clearProps: "transform,opacity" });
    gsap.from(q(".login-story > *"), { y: 16, opacity: 0, duration: 0.6, stagger: 0.1, ease: "power2.out", clearProps: "transform,opacity" });
  }, []);

  if (me.data && !needsSignIn(me.data)) return <Navigate to={next} replace />; // already signed in, or server auth is off
  const known = err && ERRORS.includes(err);

  return (
    <div
      ref={root}
      data-testid="login-page"
      style={{
        position: "relative",
        minHeight: "100svh",
        overflow: "hidden",
        display: "grid",
        placeItems: "center",
        padding: "calc(var(--inset-top, 5rem) + 1rem) 1.2rem calc(var(--inset-bottom, 3rem) + 2rem)",
        background: "linear-gradient(180deg,#2d2a5a 0%,#6b3a68 52%,#f0a35a 100%)", // same dusk sky as the landing hero
        color: "#f3ead3",
      }}
    >
      <Stars count={60} />
      <div aria-hidden="true" style={{ position: "absolute", insetInline: 0, bottom: "10%", height: "58%", color: "#150f24" }}>
        <Skyline initialTheme="dusk" />
      </div>
      <div aria-hidden="true" style={{ position: "absolute", insetInline: "-10%", bottom: 0, height: "34%" }}>
        <Dunes layers={3} />
      </div>

      <div className="login-grid">
        <div className="login-story">
          <span className="login-eyebrow">{t("login.eyebrow")}</span>
          <h1 className="display" style={{ margin: 0, fontSize: "clamp(2rem,5vw,3.2rem)", lineHeight: 1.08, color: "#f3ead3" }}>
            {t("login.headline")}
          </h1>
          <figure className="login-quote" data-testid="login-quote">
            <blockquote>{i18n.language === "ar" ? `«${t("login.quote")}»` : `“${t("login.quote")}”`}</blockquote>
            <figcaption>{t("login.quoteBy")}</figcaption>
          </figure>
          <ul className="login-points">
            {POINTS.map((p) => (
              <li key={p.key}>
                <span className="ico">{p.icon}</span>
                <div>
                  <strong>{t(`login.points.${p.key}.title`)}</strong>
                  <span className="body">{t(`login.points.${p.key}.body`)}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <section aria-labelledby="login-h" className="login-card glass">
          <MashrabiyaBand height={26} opacity={0.55} />
          <div className="body">
            <div style={{ textAlign: "center", display: "grid", gap: "0.5rem" }}>
              <h2 id="login-h" className="display" style={{ margin: 0, fontSize: "clamp(1.4rem,4vw,1.75rem)", color: "#f3ead3" }}>
                {t("login.title")}
              </h2>
              <p style={{ margin: 0, color: "#d6dde3", lineHeight: 1.55 }}>{t("login.subtitle")}</p>
            </div>

            {known && (
              <p role="alert" data-testid="login-error" style={{ margin: 0, padding: "0.6rem 0.8rem", borderRadius: 12, background: "rgba(176,58,46,.25)", border: "1px solid rgba(255,160,140,.6)", color: "#ffd9d0" }}>
                {t(`login.errors.${err}`, { login: params.get("login") ?? "" })}
              </p>
            )}

            {me.isLoading || cfg.isLoading ? (
              <Skeleton h={48} />
            ) : cfg.data?.github || cfg.data?.email ? (
              <>
                {cfg.data?.email && <EmailSignIn confirmed={params.get("confirmed") === "1"} />}
                {cfg.data?.email && cfg.data?.github && <div className="login-divider">{t("login.or")}</div>}
                {cfg.data?.github && (
                  <a
                    className="btn"
                    data-testid="github-signin"
                    href={`/api/auth/github/login?next=${encodeURIComponent(next)}`}
                    style={{ justifySelf: "center", display: "inline-flex", gap: 10, alignItems: "center", minHeight: 48 }}
                  >
                    <GitHubMark /> {t("login.github")}
                  </a>
                )}
              </>
            ) : (
              <p role="alert" style={{ margin: 0, color: "#ffd9d0" }}>{t("login.notConfigured")}</p>
            )}

            <div style={{ display: "grid", gap: "0.35rem", textAlign: "center" }}>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "#b9c4cc" }}>{t(cfg.data?.email ? "login.approvedEmail" : "login.approvedOnly")}</p>
              {!cfg.data?.email && <p style={{ margin: 0, fontSize: "0.8rem", color: "#9fb0bb" }}>{t("login.privacy")}</p>}
              <p style={{ margin: 0, fontSize: "0.8rem", color: "#9fb0bb" }}>{t("login.secure")}</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
