// Admin Testlar hub: lists assessments as cards + "Yangi test" entry point.
// Reuses admin primitives (docs/spec/20 §5). Text nodes only; mobile-first.
import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../../api";
import { t } from "../../i18n/uz";
import type { AssessmentAdminOut } from "../../types";
import {
  AdminEmptyState,
  AdminErrorState,
  AdminListCard,
  AdminLoadingState,
  AdminPageHeader,
  AdminStatusBadge
} from "../primitives";

// Human labels for the six AssessmentType values (never show raw enum keys).
export const ASSESSMENT_TYPE_LABEL: Record<string, string> = {
  custom_test: t("atypeCustomTest"),
  practice_ticket: t("atypePracticeTicket"),
  endurance_50: t("atypeEndurance50"),
  endurance_100: t("atypeEndurance100"),
  readiness_challenge: t("atypeReadinessChallenge"),
  daily_challenge: t("atypeDailyChallenge")
};

export const SELECTION_MODE_LABEL: Record<string, string> = {
  manual: t("selModeManual"),
  random_filter: t("selModeRandom")
};

export function assessmentTypeLabel(type: string): string {
  return ASSESSMENT_TYPE_LABEL[type] || type;
}

export function selectionModeLabel(mode: string | null | undefined): string {
  if (!mode) return "";
  return SELECTION_MODE_LABEL[mode] || mode;
}

export function AssessmentHub({ onOpenEditor }: { onOpenEditor: (id?: string) => void }) {
  const [items, setItems] = useState<AssessmentAdminOut[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    setErr(null);
    setItems(null);
    adminApi
      .listAssessments()
      .then((r) => setItems(r.assessments))
      .catch((e) => setErr(String(e.message)));
  }, []);
  useEffect(load, [load]);

  return (
    <div className="admin-page">
      <AdminPageHeader
        title={t("assessmentsTitle")}
        subtitle={t("assessmentsHint")}
        actions={
          <button type="button" className="admin-btn admin-btn--primary" onClick={() => onOpenEditor()}>
            {t("assessmentNew")}
          </button>
        }
      />
      {err ? (
        <AdminErrorState message={t("assessmentLoadFailed")} onRetry={load} />
      ) : items === null ? (
        <AdminLoadingState />
      ) : items.length === 0 ? (
        <AdminEmptyState message={t("assessmentEmpty")} />
      ) : (
        items.map((a) => {
          const v = a.latest_version;
          const count = v ? v.question_count : 0;
          const eligible = v ? v.eligible_count : 0;
          const metaParts: string[] = [assessmentTypeLabel(a.type)];
          if (v) metaParts.push(selectionModeLabel(v.selection_mode));
          metaParts.push(`${count} ${t("savolWord")}`);
          metaParts.push(`${t("eligibleCountLabel")}: ${eligible}/${count}`);
          return (
            <AdminListCard
              key={a.id}
              title={v && v.title ? v.title : a.slug}
              badge={<AdminStatusBadge status={a.status} />}
              meta={metaParts.join(" · ")}
              onClick={() => onOpenEditor(a.id)}
            />
          );
        })
      )}
    </div>
  );
}
