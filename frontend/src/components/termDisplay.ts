import { useTranslation } from "react-i18next";
import type { ContractData } from "../api/client";
import { useFmt } from "../i18n/format";

export type FieldKey =
  | "buyer"
  | "unit_id"
  | "price"
  | "area_sqft"
  | "handover_date"
  | "grace_period_days"
  | "delay_rate"
  | "delay_basis"
  | "delay_cap"
  | "cancellation_clause";

export const FIELDS: FieldKey[] = [
  "buyer",
  "unit_id",
  "price",
  "area_sqft",
  "handover_date",
  "grace_period_days",
  "delay_rate",
  "delay_basis",
  "delay_cap",
  "cancellation_clause",
];

/** The extracted terms, grouped the way a reader thinks about a contract. */
export const GROUPS: { key: string; fields: FieldKey[] }[] = [
  { key: "parties", fields: ["buyer", "unit_id"] },
  { key: "price", fields: ["price", "area_sqft"] },
  { key: "delay", fields: ["handover_date", "grace_period_days", "delay_rate", "delay_basis", "delay_cap"] },
  { key: "cancel", fields: ["cancellation_clause"] },
];

/** How each extracted term is shown to a person (one place, so the summary cards and the table always agree). */
export function useTermDisplay() {
  const { t } = useTranslation();
  const fmt = useFmt();
  return (k: FieldKey, cc: ContractData): { text: string; missing: boolean } => {
    const item = cc[k];
    const v = item.value as unknown;
    if (k === "cancellation_clause")
      return v != null ? { text: t("terms.present"), missing: false } : { text: t("terms.notFound"), missing: true };
    if (k === "delay_cap") {
      if (v != null) return { text: t("terms.capValue", { value: `${fmt.flex(v as number)}%` }), missing: false };
      return item.source_quote ? { text: t("terms.noCap"), missing: false } : { text: t("common.notStated"), missing: true };
    }
    if (v == null) return { text: t("common.notStated"), missing: true };
    switch (k) {
      case "price":
        return { text: fmt.aed(v as number, 0), missing: false };
      case "area_sqft":
        return { text: t("terms.sqft", { value: fmt.num(v as number, 2) }), missing: false };
      case "handover_date":
        return { text: fmt.date(v as string), missing: false };
      case "grace_period_days":
        return { text: t("terms.daysValue", { value: fmt.num(v as number) }), missing: false };
      case "delay_basis":
        return { text: t(`terms.basis.${String(v)}`), missing: false };
      case "delay_rate": {
        const basis = cc.delay_basis.value;
        return {
          text:
            basis === "fixed_per_sqft_per_year"
              ? t("terms.rateFixed", { value: fmt.aed(v as number, 2) })
              : basis === "percent_per_annum"
                ? t("terms.ratePercent", { value: `${fmt.flex(v as number)}%` })
                : fmt.flex(v as number),
          missing: false,
        };
      }
      default:
        return { text: String(v), missing: false };
    }
  };
}

/** Number of values still waiting for a person (flagged and not yet reviewed). Same rule as the server's review queue. */
export function countOpenReviews(c: ContractData): number {
  const flagged = (x: { needs_review?: boolean; human_verified?: boolean } | undefined) => !!x && !!x.needs_review && !x.human_verified;
  return (
    FIELDS.filter((k) => flagged(c[k])).length +
    c.payment_plan.filter(flagged).length +
    (c.ungrounded_rows ?? []).filter(flagged).length +
    (c.dated_clauses ?? []).filter(flagged).length
  );
}
