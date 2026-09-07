// Guided single-question CREATE wizard (Uzbek Latin). One question at a time, 5 steps.
// Mirrors the SAT QuestionStudio UX but keeps prava's role-gated, immutable-version
// lifecycle: author saves + submits for review; only a reviewer/admin publishes. Server
// enforces every transition (docs/spec/09, /19); this UI gate is convenience only. All
// author content renders as React text nodes (auto-escaped) — never dangerouslySetInnerHTML.
import { useState } from "react";
import { adminApi } from "../api";
import { TOPIC_LABELS, topicLabel } from "../i18n/uz";
import type { AdminQuestionInput, AdminRuleOut } from "../types";
import { emptyQuestion, LivePreview, RulePicker, StatusBadge } from "./legacy";

const TOPIC_KEYS = Object.keys(TOPIC_LABELS);

// Exactly 5 steps, Uzbek labels (see WHAT TO BUILD §3).
const WIZARD_STEPS = ["Asosiy", "Savol matni va media", "Variantlar", "Tushuntirish va qoida", "Ko'rib chiqish va QA"];

interface ReadinessCheck {
  key: string;
  label: string;
  passed: boolean;
}

// Client-side mirror of backend validate_version_for_publish (docs/spec/09 §QA).
// This is guidance only; the server re-validates on publish. ``ruleStatus`` maps a
// picked rule code -> its status ("active"|"superseded"|...) so we mirror the backend
// requirement of at least one CURRENT (active) linked rule; unknown -> treated active.
function readinessChecks(d: AdminQuestionInput, ruleStatus: Record<string, string>): ReadinessCheck[] {
  const filled = d.options.filter((o) => o.text.trim() !== "");
  const correctCount = d.options.filter((o) => o.is_correct).length;
  const everyOptionComplete =
    d.options.length > 0 && d.options.every((o) => o.text.trim() !== "" && o.explanation.trim() !== "");
  return [
    { key: "one_correct", label: "Aynan bitta to'g'ri variant belgilangan", passed: correctCount === 1 },
    { key: "option_count", label: "2 tadan 5 tagacha variant mavjud", passed: d.options.length >= 2 && d.options.length <= 5 },
    { key: "prompt_present", label: "Savol matni to'ldirilgan", passed: d.prompt.trim() !== "" },
    { key: "short_explanation", label: "Qisqa izoh (eslab qoling) to'ldirilgan", passed: d.short_explanation.trim() !== "" },
    { key: "options_complete", label: "Har bir variantda matn va izoh bor", passed: everyOptionComplete && filled.length === d.options.length },
    { key: "rule_linked", label: "Kamida bitta amaldagi qoida biriktirilgan", passed: d.rule_codes.some((c) => (ruleStatus[c] ?? "active") === "active") }
  ];
}

// Step-level validity that gates the "Keyingi" (Next) button.
function stepValid(step: number, d: AdminQuestionInput): boolean {
  if (step === 1) return d.prompt.trim() !== ""; // media is additive, never a substitute for prompt
  if (step === 2) {
    const filled = d.options.filter((o) => o.text.trim() !== "");
    const correctCount = d.options.filter((o) => o.is_correct).length;
    return d.options.length >= 2 && d.options.length <= 5 && filled.length === d.options.length && correctCount === 1;
  }
  return true; // steps 0, 3, 4 are freely advanceable
}

export function QuestionWizard({
  canReview,
  onSaved,
  onExitToList
}: {
  canReview: boolean;
  onSaved?: (versionId: string, questionId: string) => void;
  onExitToList?: () => void;
}) {
  const [data, setData] = useState<AdminQuestionInput>(emptyQuestion());
  const [step, setStep] = useState(0);
  const [versionId, setVersionId] = useState<string | null>(null);
  const [questionId, setQuestionId] = useState<string | null>(null);
  const [statusNow, setStatusNow] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [transitioning, setTransitioning] = useState(false);
  // Tracks the status ("active"/"superseded"/...) of rules picked this session so the
  // readiness checklist mirrors the backend "at least one CURRENT rule" publish gate.
  const [ruleStatus, setRuleStatus] = useState<Record<string, string>>({});

  // ---- option helpers (min 2, max 5, exactly one correct) ----
  const setOption = (idx: number, patch: Partial<AdminQuestionInput["options"][number]>) =>
    setData((d) => ({ ...d, options: d.options.map((o, i) => (i === idx ? { ...o, ...patch } : o)) }));
  const setCorrect = (idx: number) =>
    setData((d) => ({ ...d, options: d.options.map((o, i) => ({ ...o, is_correct: i === idx })) }));
  const addOption = () =>
    setData((d) => (d.options.length >= 5 ? d : { ...d, options: [...d.options, { text: "", explanation: "", is_correct: false }] }));
  const removeOption = (idx: number) =>
    setData((d) => {
      if (d.options.length <= 2) return d;
      const remaining = d.options.filter((_, i) => i !== idx);
      // Guarantee exactly one correct remains after removing the correct option.
      if (!remaining.some((o) => o.is_correct)) remaining[0] = { ...remaining[0], is_correct: true };
      return { ...d, options: remaining };
    });

  async function uploadMedia(file: File) {
    setErr(null);
    try {
      const m = await adminApi.uploadMedia(file);
      setData((d) => ({ ...d, media_id: m.id }));
      setMsg("Media yuklandi");
    } catch (e) {
      setErr(String((e as Error).message));
    }
  }

  // Create on first save; edit the same working version on subsequent saves this session.
  async function save(): Promise<boolean> {
    setErr(null);
    setMsg(null);
    setSaving(true);
    try {
      const res = versionId ? await adminApi.editQuestion(questionId!, data) : await adminApi.createQuestion(data);
      setVersionId(res.id);
      setQuestionId(res.question_id);
      setStatusNow(res.status);
      setMsg("Saqlandi (qoralama)");
      onSaved?.(res.id, res.question_id);
      return true;
    } catch (e) {
      setErr(String((e as Error).message));
      return false;
    } finally {
      setSaving(false);
    }
  }

  // Save, then reset to a fresh question for the rapid one-by-one loop. Preserves the
  // last-used topic/difficulty/is_sign_question for convenience; everything else clears.
  async function saveAndAddAnother() {
    const ok = await save();
    if (!ok) return;
    const fresh = emptyQuestion();
    fresh.topic = data.topic;
    fresh.difficulty = data.difficulty;
    fresh.is_sign_question = data.is_sign_question;
    setData(fresh);
    setVersionId(null);
    setQuestionId(null);
    setStatusNow(null);
    setRuleStatus({});
    setStep(0);
    setMsg("Saqlandi — yangi savol qo'shishingiz mumkin");
  }

  // Role-gated lifecycle transitions. Mirrors Editor.transition() exactly. Publish is
  // never reachable before a draft exists, and never for an author (!canReview).
  async function transition(kind: "submit" | "review" | "publish") {
    if (!versionId) return;
    setErr(null);
    setMsg(null);
    setTransitioning(true);
    try {
      const res =
        kind === "submit"
          ? await adminApi.submitReview(versionId)
          : kind === "review"
            ? await adminApi.review(versionId)
            : await adminApi.publish(versionId);
      setStatusNow(res.status);
      setMsg(`Amal bajarildi: ${kind} → ${res.status}`);
    } catch (e) {
      setErr(String((e as Error).message));
    } finally {
      setTransitioning(false);
    }
  }

  const canAdvance = stepValid(step, data);
  const checks = readinessChecks(data, ruleStatus);
  const publishReady = checks.every((c) => c.passed);
  const isLast = step === WIZARD_STEPS.length - 1;

  return (
    <div className="wizard">
      <div className="wizard-head">
        <div>
          <p className="wizard-eyebrow">Yangi savol (B toifasi)</p>
          <h2>
            {step + 1}/{WIZARD_STEPS.length}-qadam: {WIZARD_STEPS[step]}
          </h2>
        </div>
        {onExitToList && (
          <button type="button" className="secondary" onClick={onExitToList}>
            Ro'yxatga
          </button>
        )}
      </div>

      <div className="wizard-progress" aria-hidden="true">
        <span style={{ width: `${((step + 1) / WIZARD_STEPS.length) * 100}%` }} />
      </div>
      <ol className="wizard-steps">
        {WIZARD_STEPS.map((title, index) => (
          <li key={title} className={index === step ? "active" : index < step ? "done" : ""}>
            <span className="wizard-steps__num">{index + 1}</span>
            <span className="wizard-steps__label">{title}</span>
          </li>
        ))}
      </ol>

      <div className="wizard-step">
        {step === 0 && (
          <>
            <p className="muted">Toifa: B (o'zgartirib bo'lmaydi)</p>
            <label className="muted">Mavzu</label>
            <select value={data.topic} onChange={(e) => setData({ ...data, topic: e.target.value })}>
              {TOPIC_KEYS.map((tp) => (
                <option key={tp} value={tp}>
                  {topicLabel(tp)}
                </option>
              ))}
            </select>
            <label className="muted">Qiyinlik (1-3)</label>
            <input
              type="number"
              min={1}
              max={3}
              value={data.difficulty}
              onChange={(e) => setData({ ...data, difficulty: Number(e.target.value) })}
            />
            <label>
              <input
                type="checkbox"
                checked={data.is_sign_question}
                onChange={(e) => setData({ ...data, is_sign_question: e.target.checked })}
              />{" "}
              Yo'l belgisi savoli
            </label>
          </>
        )}

        {step === 1 && (
          <>
            <label className="muted">Savol matni (uz)</label>
            <textarea value={data.prompt} onChange={(e) => setData({ ...data, prompt: e.target.value })} />
            <label className="muted">Media (rasm/gif/video)</label>
            <input type="file" onChange={(e) => e.target.files && e.target.files[0] && uploadMedia(e.target.files[0])} />
            {data.media_id && (
              <div className="wizard-media">
                <p className="muted">media_id: {data.media_id}</p>
                <button type="button" className="secondary" onClick={() => setData({ ...data, media_id: null })}>
                  Mediani olib tashlash
                </button>
              </div>
            )}
            <p className="muted">Keyingi qadam uchun: savol matni to'ldirilishi shart. Media ixtiyoriy.</p>
          </>
        )}

        {step === 2 && (
          <>
            <h3>Variantlar (2-5, bitta to'g'ri)</h3>
            {data.options.map((o, i) => (
              <div key={i} className="opt-edit">
                <label>
                  <input type="radio" name="wizard-correct" checked={o.is_correct} onChange={() => setCorrect(i)} /> to'g'ri
                </label>
                <input placeholder={`Variant ${i + 1}`} value={o.text} onChange={(e) => setOption(i, { text: e.target.value })} />
                <input placeholder="Izoh" value={o.explanation} onChange={(e) => setOption(i, { explanation: e.target.value })} />
                <button type="button" className="secondary" disabled={data.options.length <= 2} onClick={() => removeOption(i)}>
                  o'chirish
                </button>
              </div>
            ))}
            <button type="button" className="secondary" disabled={data.options.length >= 5} onClick={addOption}>
              + variant
            </button>
          </>
        )}

        {step === 3 && (
          <>
            <label className="muted">Qisqa izoh (eslab qoling)</label>
            <textarea
              value={data.short_explanation}
              onChange={(e) => setData({ ...data, short_explanation: e.target.value })}
            />
            <RulePicker
              selected={data.rule_codes}
              onChange={(codes) => setData({ ...data, rule_codes: codes })}
              onPick={(rule: AdminRuleOut) => setRuleStatus((m) => ({ ...m, [rule.code]: rule.status }))}
            />
          </>
        )}

        {step === 4 && (
          <>
            <p className="muted">Talaba ko'rinishi (mashq/imtihon/mobil) va nashrga tayyorlik ro'yxati.</p>
            <LivePreview data={data} />
            <h3>Nashrga tayyorlik</h3>
            <ul className="checklist">
              {checks.map((c) => (
                <li key={c.key} className={c.passed ? "pass" : "fail"}>
                  {c.passed ? "✓" : "✗"} {c.label}
                </li>
              ))}
            </ul>
            {statusNow && <p className="muted">Holat: <StatusBadge status={statusNow} /></p>}
          </>
        )}
      </div>

      <div className="wizard-actions">
        <button type="button" className="secondary" disabled={step === 0} onClick={() => setStep((s) => Math.max(0, s - 1))}>
          Orqaga
        </button>
        {!isLast && (
          <button type="button" disabled={!canAdvance} onClick={() => setStep((s) => Math.min(WIZARD_STEPS.length - 1, s + 1))}>
            Keyingi
          </button>
        )}
        {isLast && (
          <div className="wizard-final-actions">
            <button type="button" className="secondary" disabled={saving} onClick={save}>
              {saving ? "Saqlanmoqda..." : "Saqlash (qoralama)"}
            </button>
            <button type="button" className="secondary" disabled={saving} onClick={saveAndAddAnother}>
              Saqlash va yana qo'shish
            </button>
            {versionId && (
              <>
                <button type="button" className="secondary" disabled={transitioning} onClick={() => transition("submit")}>
                  Ko'rikka yuborish
                </button>
                {canReview && (
                  <button type="button" className="secondary" disabled={transitioning} onClick={() => transition("review")}>
                    Ko'rildi
                  </button>
                )}
                {canReview && (
                  <button type="button" disabled={transitioning || !publishReady} onClick={() => transition("publish")}>
                    Nashr etish
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {msg && <p className="explain">{msg}</p>}
      {err && <p className="explain">{err}</p>}
    </div>
  );
}
