// Admin Testlar editor: create-then-configure flow for a single assessment.
// Reuses admin primitives (docs/spec/20 §5). Text nodes only; TS strict; mobile-first.
// Backend is authoritative for locked counts and publish eligibility (422 surfaced).
import { useCallback, useEffect, useRef, useState } from "react";
import { adminApi } from "../../api";
import { t, TOPIC_LABELS, topicLabel } from "../../i18n/uz";
import type {
  AssessmentAdminOut,
  AssessmentRevealMode,
  AssessmentSelectionMode,
  AssessmentType,
  AssessmentUpdateInput,
  AdminQuestionListItem
} from "../../types";
import {
  AdminConfirmSheet,
  AdminField,
  AdminFilterChip,
  AdminLoadingState,
  AdminErrorState,
  AdminSearchField,
  AdminSelect,
  AdminStatusBadge,
  AdminTextarea,
  AdminToast,
  type MutationState
} from "../primitives";
import { assessmentTypeLabel } from "./AssessmentHub";

const TYPE_OPTIONS: { value: AssessmentType; label: string }[] = [
  { value: "custom_test", label: t("atypeCustomTest") },
  { value: "practice_ticket", label: t("atypePracticeTicket") },
  { value: "endurance_50", label: t("atypeEndurance50") },
  { value: "endurance_100", label: t("atypeEndurance100") },
  { value: "readiness_challenge", label: t("atypeReadinessChallenge") },
  { value: "daily_challenge", label: t("atypeDailyChallenge") }
];

const SELECTION_OPTIONS: { value: AssessmentSelectionMode; label: string }[] = [
  { value: "manual", label: t("selModeManual") },
  { value: "random_filter", label: t("selModeRandom") }
];

const REVEAL_OPTIONS: { value: AssessmentRevealMode; label: string }[] = [
  { value: "each_answer", label: t("revealEachAnswer") },
  { value: "completion", label: t("revealCompletion") }
];

const DIFFICULTY_LABEL: Record<number, string> = { 1: t("difficulty1"), 2: t("difficulty2"), 3: t("difficulty3") };
const LOCKED_COUNTS: Record<string, number> = { endurance_50: 50, endurance_100: 100 };

function secondsToMinutes(seconds: number | null): string {
  if (seconds == null) return "";
  return String(Math.round(seconds / 60));
}

// ---------------------------------------------------------------- create form
function CreateForm({ onCreated }: { onCreated: (a: AssessmentAdminOut) => void }) {
  const [type, setType] = useState<AssessmentType>("custom_test");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [state, setState] = useState<MutationState>("idle");
  const [err, setErr] = useState<string | null>(null);

  function submit() {
    if (!title.trim()) return;
    setState("saving");
    setErr(null);
    adminApi
      .createAssessment({ type, title: title.trim(), description: description.trim() || undefined })
      .then((a) => {
        setState("saved");
        onCreated(a);
      })
      .catch((e) => {
        setState("error");
        setErr(String(e.message));
      });
  }

  return (
    <div className="admin-page">
      <h2>{t("assessmentCreateTitle")}</h2>
      <AdminSelect
        label={t("assessmentTypeLabel")}
        value={type}
        onChange={(v) => setType(v as AssessmentType)}
        options={TYPE_OPTIONS}
      />
      <AdminField label={t("assessmentTitleLabel")} value={title} onChange={setTitle} />
      <AdminTextarea label={t("assessmentDescriptionLabel")} value={description} onChange={setDescription} rows={3} />
      {err && <AdminErrorState message={err} />}
      <button
        type="button"
        className="admin-btn admin-btn--primary"
        disabled={!title.trim() || state === "saving"}
        onClick={submit}
      >
        {t("assessmentCreateBtn")}
      </button>
      <AdminToast state={state === "error" ? "idle" : state} />
    </div>
  );
}

// ---------------------------------------------------------------- manual picker
function QuestionPicker({
  questionIds,
  labels,
  onAdd,
  onRemove
}: {
  questionIds: string[];
  labels: Record<string, string>;
  onAdd: (item: AdminQuestionListItem) => void;
  onRemove: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<AdminQuestionListItem[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const params: Record<string, string> = { limit: "20" };
      if (query.trim()) params.q = query.trim();
      adminApi
        .listQuestions(params)
        .then((r) => setResults(r.items))
        .catch(() => setResults([]));
    }, 300);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [query]);

  return (
    <div className="admin-formrow">
      <span className="admin-formrow__label">{t("questionPickerLabel")}</span>
      <AdminSearchField value={query} onChange={setQuery} placeholder={t("questionSearchPlaceholder")} />
      <div className="assess-picker__results">
        {results.length === 0 ? (
          <p className="admin-formrow__hint">{t("noQuestionsFound")}</p>
        ) : (
          results.map((it) => {
            const selected = questionIds.includes(it.id);
            return (
              <div key={it.id} className="assess-picker__row">
                <div className="assess-picker__text">
                  <span className="assess-picker__prompt">{it.prompt || it.id}</span>
                  <span className="admin-formrow__hint">{topicLabel(it.topic)}</span>
                </div>
                <button
                  type="button"
                  className={"admin-chip" + (selected ? " is-active" : "")}
                  onClick={() => (selected ? onRemove(it.id) : onAdd(it))}
                >
                  {selected ? t("questionRemove") : t("questionAdd")}
                </button>
              </div>
            );
          })
        )}
      </div>
      <span className="admin-formrow__label">
        {t("selectedQuestions")}: {questionIds.length}
      </span>
      <ol className="assess-picker__selected">
        {questionIds.map((id) => (
          <li key={id} className="assess-picker__selrow">
            <span className="assess-picker__prompt">{labels[id] || id}</span>
            <button type="button" className="admin-chip is-active" onClick={() => onRemove(id)}>
              {t("questionRemove")}
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

// ---------------------------------------------------------------- editor
export function AssessmentEditor({ assessmentId, onBack }: { assessmentId?: string; onBack: () => void }) {
  const [id, setId] = useState<string | undefined>(assessmentId);
  const [data, setData] = useState<AssessmentAdminOut | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  // Form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [selectionMode, setSelectionMode] = useState<AssessmentSelectionMode>("manual");
  const [questionCount, setQuestionCount] = useState("0");
  const [timeLimitMin, setTimeLimitMin] = useState("");
  const [passCorrect, setPassCorrect] = useState("");
  const [reveal, setReveal] = useState<AssessmentRevealMode>("each_answer");
  const [randomize, setRandomize] = useState(false);
  const [topicFilters, setTopicFilters] = useState<string[]>([]);
  const [difficultyFilters, setDifficultyFilters] = useState<number[]>([]);
  const [questionIds, setQuestionIds] = useState<string[]>([]);
  const [qLabels, setQLabels] = useState<Record<string, string>>({});

  // Eligibility + actions
  const [eligible, setEligible] = useState(0);
  const [reqCount, setReqCount] = useState(0);
  const [saveState, setSaveState] = useState<MutationState>("idle");
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [confirmArchive, setConfirmArchive] = useState(false);

  const hydrate = useCallback((a: AssessmentAdminOut) => {
    setData(a);
    const v = a.latest_version;
    if (v) {
      setTitle(v.title || "");
      setDescription(v.description || "");
      setSelectionMode(v.selection_mode);
      setQuestionCount(String(v.question_count));
      setTimeLimitMin(secondsToMinutes(v.time_limit_seconds));
      setPassCorrect(v.pass_correct == null ? "" : String(v.pass_correct));
      setReveal(v.show_explanations_after);
      setRandomize(v.randomize_order);
      setTopicFilters(v.topic_filters || []);
      setDifficultyFilters(v.difficulty_filters || []);
      setQuestionIds(v.question_ids || []);
      setEligible(v.eligible_count);
      setReqCount(v.question_count);
    }
  }, []);

  const load = useCallback(
    (aid: string) => {
      setLoadErr(null);
      adminApi
        .getAssessment(aid)
        .then(hydrate)
        .catch((e) => setLoadErr(String(e.message)));
    },
    [hydrate]
  );

  useEffect(() => {
    if (id) load(id);
  }, [id, load]);

  if (!id) {
    return (
      <CreateForm
        onCreated={(a) => {
          setId(a.id);
          hydrate(a);
        }}
      />
    );
  }

  if (loadErr) return <AdminErrorState message={loadErr} onRetry={() => load(id)} />;
  if (!data) return <AdminLoadingState />;

  const locked = LOCKED_COUNTS[data.type];
  const isLocked = locked != null;
  const effectiveCount = isLocked ? locked : selectionMode === "manual" ? questionIds.length : Number(questionCount) || 0;
  const publishable = eligible >= reqCount && reqCount >= 1;

  function toggleTopic(key: string) {
    setTopicFilters((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  }
  function toggleDifficulty(d: number) {
    setDifficultyFilters((prev) => (prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d]));
  }

  function buildPatch(): AssessmentUpdateInput {
    const patch: AssessmentUpdateInput = {
      title: title.trim(),
      description: description,
      selection_mode: selectionMode,
      show_explanations_after: reveal,
      randomize_order: randomize,
      time_limit_seconds: timeLimitMin.trim() ? Number(timeLimitMin) * 60 : null,
      pass_correct: passCorrect.trim() ? Number(passCorrect) : null
    };
    if (selectionMode === "manual") {
      patch.question_ids = questionIds;
      if (!isLocked) patch.question_count = questionIds.length;
    } else {
      patch.topic_filters = topicFilters;
      patch.difficulty_filters = difficultyFilters;
      if (!isLocked) patch.question_count = Number(questionCount) || 0;
    }
    return patch;
  }

  function save() {
    if (!id) return;
    setSaveState("saving");
    setActionErr(null);
    adminApi
      .updateAssessment(id, buildPatch())
      .then((a) => {
        hydrate(a);
        setSaveState("saved");
      })
      .catch((e) => {
        setSaveState("error");
        setActionErr(String(e.message));
      });
  }

  function refreshEligible() {
    if (!id) return;
    adminApi
      .eligibleCount(id)
      .then((r) => {
        setEligible(r.eligible_count);
        setReqCount(r.question_count);
      })
      .catch((e) => setActionErr(String(e.message)));
  }

  function publish() {
    if (!id) return;
    setActionErr(null);
    adminApi
      .publishAssessment(id)
      .then(hydrate)
      .catch((e) => setActionErr(String(e.message)));
  }

  function archive() {
    if (!id) return;
    setConfirmArchive(false);
    adminApi
      .archiveAssessment(id)
      .then(() => onBack())
      .catch((e) => setActionErr(String(e.message)));
  }

  return (
    <div className="admin-page">
      <div className="admin-pageheader">
        <div className="admin-pageheader__text">
          <h2 className="admin-pageheader__title">{title || data.slug}</h2>
          <p className="admin-pageheader__sub">{assessmentTypeLabel(data.type)}</p>
        </div>
        <div className="admin-pageheader__actions">
          <AdminStatusBadge status={data.status} />
        </div>
      </div>

      <AdminField label={t("assessmentTitleLabel")} value={title} onChange={setTitle} />
      <AdminTextarea label={t("assessmentDescriptionLabel")} value={description} onChange={setDescription} rows={3} />

      <AdminSelect
        label={t("selectionModeLabel")}
        value={selectionMode}
        onChange={(v) => setSelectionMode(v as AssessmentSelectionMode)}
        options={SELECTION_OPTIONS}
      />

      {isLocked ? (
        <div className="admin-formrow">
          <span className="admin-formrow__label">{t("questionCountLabel")}</span>
          <input className="admin-input" type="number" value={String(locked)} readOnly disabled />
          <span className="admin-formrow__hint">{t("questionCountLocked")}</span>
        </div>
      ) : selectionMode === "random_filter" ? (
        <AdminField
          label={t("questionCountLabel")}
          value={questionCount}
          onChange={setQuestionCount}
          type="number"
        />
      ) : null}

      <AdminField
        label={t("timeLimitLabel")}
        value={timeLimitMin}
        onChange={setTimeLimitMin}
        type="number"
        hint={t("timeLimitHint")}
      />
      <AdminField
        label={t("passCorrectLabel")}
        value={passCorrect}
        onChange={setPassCorrect}
        type="number"
        hint={t("passCorrectHint")}
      />

      <AdminSelect
        label={t("revealLabel")}
        value={reveal}
        onChange={(v) => setReveal(v as AssessmentRevealMode)}
        options={REVEAL_OPTIONS}
      />

      <label className="admin-formrow assess-check">
        <input type="checkbox" checked={randomize} onChange={(e) => setRandomize(e.target.checked)} />
        <span className="admin-formrow__label">{t("randomizeOrderLabel")}</span>
      </label>

      {selectionMode === "random_filter" && (
        <>
          <div className="admin-formrow">
            <span className="admin-formrow__label">{t("topicFiltersLabel")}</span>
            <div className="assess-chips">
              {Object.keys(TOPIC_LABELS).map((key) => (
                <AdminFilterChip
                  key={key}
                  label={topicLabel(key)}
                  active={topicFilters.includes(key)}
                  onClick={() => toggleTopic(key)}
                />
              ))}
            </div>
          </div>
          <div className="admin-formrow">
            <span className="admin-formrow__label">{t("difficultyFiltersLabel")}</span>
            <div className="assess-chips">
              {[1, 2, 3].map((d) => (
                <AdminFilterChip
                  key={d}
                  label={DIFFICULTY_LABEL[d]}
                  active={difficultyFilters.includes(d)}
                  onClick={() => toggleDifficulty(d)}
                />
              ))}
            </div>
          </div>
        </>
      )}

      {selectionMode === "manual" && (
        <QuestionPicker
          questionIds={questionIds}
          labels={qLabels}
          onAdd={(item) => {
            setQuestionIds((prev) => (prev.includes(item.id) ? prev : [...prev, item.id]));
            setQLabels((prev) => ({ ...prev, [item.id]: item.prompt || item.id }));
          }}
          onRemove={(qid) => setQuestionIds((prev) => prev.filter((x) => x !== qid))}
        />
      )}

      <div className={"admin-toast " + (publishable ? "admin-toast--saved" : "admin-toast--error")}>
        <span>
          {t("eligiblePanelTitle")}: {eligible} / {reqCount} · {publishable ? t("eligibleOk") : t("eligibleWarn")}
        </span>
        <button type="button" className="admin-toast__retry" onClick={refreshEligible}>
          {t("eligibleRefresh")}
        </button>
      </div>
      <span className="admin-formrow__hint">
        {t("requiredCountLabel")}: {effectiveCount}
      </span>

      {actionErr && <AdminErrorState message={actionErr} />}
      <AdminToast state={saveState} onRetry={save} />

      <div className="admin-sticky-actions">
        <button type="button" className="admin-btn admin-btn--primary" onClick={save} disabled={saveState === "saving"}>
          {t("assessmentSave")}
        </button>
        <button
          type="button"
          className="admin-btn admin-btn--secondary"
          onClick={publish}
          disabled={!publishable}
        >
          {t("assessmentPublish")}
        </button>
        <button type="button" className="admin-btn admin-btn--danger" onClick={() => setConfirmArchive(true)}>
          {t("assessmentArchive")}
        </button>
      </div>

      <AdminConfirmSheet
        open={confirmArchive}
        title={t("assessmentArchive")}
        message={t("assessmentArchiveConfirm")}
        confirmLabel={t("assessmentArchive")}
        danger
        onConfirm={archive}
        onCancel={() => setConfirmArchive(false)}
      />
    </div>
  );
}
