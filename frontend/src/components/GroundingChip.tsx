import { useTranslation } from "react-i18next";
import { useFmt } from "../i18n/format";

interface Item {
  grounding?: { status: string } | null;
  confidence?: number | null;
  needs_review?: boolean;
  human_verified?: boolean;
}

const FALLBACK = { cls: "muted", icon: "–" };
const LOOK: Record<string, { cls: string; icon: string }> = {
  grounded: { cls: "ok", icon: "✓" },
  human: { cls: "ok", icon: "✓" },
  partial: { cls: "warn", icon: "!" },
  ungrounded: { cls: "bad", icon: "✕" },
  not_stated: { cls: "muted", icon: "–" },
};

/** One badge says how far a value can be trusted: verified in the PDF, partly matched, not confirmed, checked by a person, or not stated. */
export function GroundingChip({ item }: { item: Item }) {
  const { t } = useTranslation();
  const fmt = useFmt();
  const s = item.human_verified ? "human" : (item.grounding?.status ?? "not_stated");
  const look = LOOK[s] ?? FALLBACK;
  return (
    <span
      data-testid="grounding-chip"
      data-status={s}
      className={`badge ${look.cls}`}
      title={t("evidence.confidenceHelp")}
    >
      <span aria-hidden="true">{look.icon}</span>
      {t(`evidence.status.${s}`)}
      {item.confidence != null && s !== "not_stated" && s !== "human" ? (
        <span style={{ fontWeight: 500, opacity: 0.85 }}> · {fmt.pct(item.confidence * 100, 0)}</span>
      ) : null}
    </span>
  );
}
