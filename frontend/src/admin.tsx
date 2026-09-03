// Admin studio (Uzbek). Security is enforced SERVER-SIDE on every endpoint (docs/spec/09);
// the UI role-gate is only a convenience. All author content is rendered as TEXT (React
// text nodes, auto-escaped) — raw HTML injection is never used. No answer leak anywhere.
import { useCallback, useEffect, useMemo, useState } from "react";
import { adminApi, theoryApi } from "./api";
import { TOPIC_LABELS, topicLabel } from "./i18n/uz";
import type {
  AdminOverview,
  AdminQuestionInput,
  AdminQuestionListItem,
  AdminBlockInput,
  AdminReport,
  AdminRuleOut,
  GestureContentInput,
  GestureCreateInput,
  LightContentInput,
  LightCreateInput,
  MarkingContentInput,
  MarkingCreateInput,
  QaPayload,
  ReviewQueueOut,
  SignContentInput,
  SignCreateInput,
  TheoryVersionOut
} from "./types";

const TOPIC_KEYS = Object.keys(TOPIC_LABELS);

// Lifecycle status labels + badge (docs/spec/19 §4.3). Uzbek copy for all 7 states.
const STATUS_LABELS: Record<string, string> = {
  draft: "Qoralama",
  needs_review: "Ko'rik kutilmoqda",
  reviewed: "Ko'rildi",
  published: "Nashr etilgan",
  needs_reverification: "Qayta tekshirish kerak",
  superseded: "Eskirgan",
  archived: "Arxivlangan"
};
const STATUS_KEYS = Object.keys(STATUS_LABELS);

function StatusBadge({ status }: { status: string }) {
  return <span className={"badge badge-" + status}>{STATUS_LABELS[status] || status}</span>;
}

type PreviewMode = "practice" | "exam" | "mobile";

function emptyQuestion(): AdminQuestionInput {
  return {
    category: "B",
    topic: "general_rules",
    prompt: "",
    short_explanation: "",
    difficulty: 1,
    is_sign_question: false,
    rule_codes: [],
    media_id: null,
    options: [
      { text: "", explanation: "", is_correct: true },
      { text: "", explanation: "", is_correct: false }
    ]
  };
}

// --------------------------------------------------------------------------- //
// Dashboard v2
// --------------------------------------------------------------------------- //
function Dashboard({ onGoReports, onGoReview }: { onGoReports: () => void; onGoReview: () => void }) {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [queueCount, setQueueCount] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    adminApi.overview().then(setData).catch((e) => setErr(String(e.message)));
    adminApi
      .theoryReviewQueue()
      .then((q) =>
        setQueueCount(
          q.articles.length + q.signs.length + q.markings.length + q.gestures.length + q.lights.length
        )
      )
      .catch(() => setQueueCount(null));
  }, []);
  if (err) return <p className="explain">{err}</p>;
  if (!data) return <p>Yuklanmoqda...</p>;
  const maxCov = Math.max(1, ...Object.values(data.topic_coverage));
  return (
    <div>
      <h2>Boshqaruv paneli</h2>
      <h3>Kontent holati</h3>
      <div className="admin-grid">
        {Object.entries(data.counts).map(([k, v]) => (
          <div key={k} className="admin-stat">
            <div className="admin-stat-value">{v}</div>
            <div className="muted">{STATUS_LABELS[k] || k}</div>
          </div>
        ))}
      </div>
      <h3>Tezkor havolalar</h3>
      <div className="admin-grid">
        <button type="button" className="admin-stat admin-stat-link" onClick={onGoReports}>
          <div className="admin-stat-value">{data.open_reports}</div>
          <div className="muted">Ochiq shikoyatlar</div>
        </button>
        <button type="button" className="admin-stat admin-stat-link" onClick={onGoReview}>
          <div className="admin-stat-value">{queueCount === null ? "—" : queueCount}</div>
          <div className="muted">Ko'rik navbati</div>
        </button>
        <div className="admin-stat">
          <div className="admin-stat-value">{data.media_storage.object_count}</div>
          <div className="muted">Media obyektlari</div>
        </div>
      </div>
      <h3>Mavzu qamrovi</h3>
      {Object.entries(data.topic_coverage).map(([topic, n]) => (
        <div key={topic} className="admin-bar-row">
          <span className="admin-bar-label">{topicLabel(topic)}</span>
          <span className="admin-bar">
            <span className="admin-bar-fill" style={{ width: `${(n / maxCov) * 100}%` }} />
          </span>
          <span className="admin-bar-count">{n}</span>
        </div>
      ))}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Shared: RulePicker (rule_codes chips) — reused by question + theory editors
// --------------------------------------------------------------------------- //
function RulePicker({ selected, onChange }: { selected: string[]; onChange: (codes: string[]) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<AdminRuleOut[]>([]);
  useEffect(() => {
    const id = window.setTimeout(() => {
      adminApi.searchRules(q).then((r) => setResults(r.rules)).catch(() => setResults([]));
    }, 250);
    return () => window.clearTimeout(id);
  }, [q]);
  return (
    <div className="rule-picker">
      <label className="muted">Qoida qidiruv (kod yoki matn)</label>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="masalan: 13.9 yoki chorraha" />
      <div className="rule-results">
        {results.map((r) => {
          const picked = selected.includes(r.code);
          return (
            <button
              key={r.id}
              type="button"
              className={"rule-chip" + (picked ? " picked" : "") + (r.status !== "active" ? " superseded" : "")}
              onClick={() => onChange(picked ? selected.filter((c) => c !== r.code) : [...selected, r.code])}
            >
              {r.code} — {r.title || r.text.slice(0, 40)}
              {r.status !== "active" ? " (eskirgan!)" : ""}
            </button>
          );
        })}
      </div>
      <p className="muted">Tanlangan: {selected.join(", ") || "—"}</p>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Question editor (existing flow, unchanged behaviour; topics now use Uzbek labels)
// --------------------------------------------------------------------------- //
function LivePreview({ data }: { data: AdminQuestionInput }) {
  const [mode, setMode] = useState<PreviewMode>("practice");
  return (
    <div className={"preview " + (mode === "mobile" ? "preview-mobile" : "")}>
      <div className="preview-tabs">
        <button type="button" className={mode === "practice" ? "active" : ""} onClick={() => setMode("practice")}>Mashq</button>
        <button type="button" className={mode === "exam" ? "active" : ""} onClick={() => setMode("exam")}>Imtihon</button>
        <button type="button" className={mode === "mobile" ? "active" : ""} onClick={() => setMode("mobile")}>Mobil</button>
      </div>
      <p><strong>{data.prompt || "(savol matni)"}</strong></p>
      {data.options.map((o, i) => (
        <div key={i}>
          <div className={"option" + (mode !== "exam" && o.is_correct ? " correct" : "")}>{o.text || `(variant ${i + 1})`}</div>
          {/* Exam mode reveals NO explanations/correctness (docs/spec/09). */}
          {mode !== "exam" && o.explanation && <div className="explain">{o.explanation}</div>}
        </div>
      ))}
      {mode !== "exam" && data.short_explanation && (
        <p className="explain">Eslab qoling: {data.short_explanation}</p>
      )}
      {mode !== "exam" && data.rule_codes.length > 0 && (
        <p className="muted">Qoida: {data.rule_codes.join(", ")}</p>
      )}
    </div>
  );
}

function Editor({
  editingId,
  canReview,
  onSaved
}: {
  editingId: string | null;
  canReview: boolean;
  onSaved: (versionId: string, questionId: string) => void;
}) {
  const [data, setData] = useState<AdminQuestionInput>(emptyQuestion());
  const [versionId, setVersionId] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const setOption = (idx: number, patch: Partial<AdminQuestionInput["options"][number]>) => {
    setData((d) => ({ ...d, options: d.options.map((o, i) => (i === idx ? { ...o, ...patch } : o)) }));
  };
  const setCorrect = (idx: number) => {
    setData((d) => ({ ...d, options: d.options.map((o, i) => ({ ...o, is_correct: i === idx })) }));
  };
  const addOption = () =>
    setData((d) => (d.options.length >= 5 ? d : { ...d, options: [...d.options, { text: "", explanation: "", is_correct: false }] }));
  const removeOption = (idx: number) =>
    setData((d) => (d.options.length <= 2 ? d : { ...d, options: d.options.filter((_, i) => i !== idx) }));

  async function save() {
    setErr(null);
    setMsg(null);
    try {
      const res = editingId ? await adminApi.editQuestion(editingId, data) : await adminApi.createQuestion(data);
      setVersionId(res.id);
      setMsg(`Saqlandi (versiya ${res.version}, holat: ${res.status})`);
      onSaved(res.id, res.question_id);
    } catch (e) {
      setErr(String((e as Error).message));
    }
  }

  async function uploadMedia(file: File) {
    try {
      const m = await adminApi.uploadMedia(file);
      setData((d) => ({ ...d, media_id: m.id }));
      setMsg("Media yuklandi");
    } catch (e) {
      setErr(String((e as Error).message));
    }
  }

  async function transition(kind: "submit" | "review" | "publish") {
    if (!versionId) return;
    setErr(null);
    try {
      if (kind === "submit") await adminApi.submitReview(versionId);
      else if (kind === "review") await adminApi.review(versionId);
      else await adminApi.publish(versionId);
      setMsg(`Amal bajarildi: ${kind}`);
    } catch (e) {
      setErr(String((e as Error).message));
    }
  }

  return (
    <div className="editor-layout">
      <div className="editor-form">
        <h2>{editingId ? "Savolni tahrirlash" : "Yangi savol"}</h2>
        {editingId && <p className="explain">Nashr etilgan savol tahriri yangi versiya yaratadi.</p>}
        <label className="muted">Mavzu</label>
        <select value={data.topic} onChange={(e) => setData({ ...data, topic: e.target.value })}>
          {TOPIC_KEYS.map((tp) => <option key={tp} value={tp}>{topicLabel(tp)}</option>)}
        </select>
        <label className="muted">Savol matni (uz)</label>
        <textarea value={data.prompt} onChange={(e) => setData({ ...data, prompt: e.target.value })} />
        <label className="muted">Qisqa izoh (eslab qoling)</label>
        <textarea value={data.short_explanation} onChange={(e) => setData({ ...data, short_explanation: e.target.value })} />
        <label className="muted">Qiyinlik (1-3)</label>
        <input type="number" min={1} max={3} value={data.difficulty}
          onChange={(e) => setData({ ...data, difficulty: Number(e.target.value) })} />
        <label>
          <input type="checkbox" checked={data.is_sign_question}
            onChange={(e) => setData({ ...data, is_sign_question: e.target.checked })} /> Yo'l belgisi savoli
        </label>

        <h3>Variantlar (2-5, bitta to'g'ri)</h3>
        {data.options.map((o, i) => (
          <div key={i} className="opt-edit">
            <label>
              <input type="radio" name="correct" checked={o.is_correct} onChange={() => setCorrect(i)} /> to'g'ri
            </label>
            <input placeholder={`Variant ${i + 1}`} value={o.text} onChange={(e) => setOption(i, { text: e.target.value })} />
            <input placeholder="Izoh" value={o.explanation} onChange={(e) => setOption(i, { explanation: e.target.value })} />
            <button type="button" className="secondary" onClick={() => removeOption(i)}>o'chirish</button>
          </div>
        ))}
        <button type="button" className="secondary" onClick={addOption}>+ variant</button>

        <RulePicker selected={data.rule_codes} onChange={(codes) => setData({ ...data, rule_codes: codes })} />

        <label className="muted">Media (rasm/gif/video)</label>
        <input type="file" onChange={(e) => e.target.files && e.target.files[0] && uploadMedia(e.target.files[0])} />
        {data.media_id && <p className="muted">media_id: {data.media_id}</p>}

        <div style={{ height: 12 }} />
        <button onClick={save}>Saqlash</button>
        {versionId && (
          <div className="review-actions">
            <button className="secondary" onClick={() => transition("submit")}>Ko'rikka yuborish</button>
            {canReview && <button className="secondary" onClick={() => transition("review")}>Ko'rildi</button>}
            {canReview && <button onClick={() => transition("publish")}>Nashr etish</button>}
          </div>
        )}
        {msg && <p className="explain">{msg}</p>}
        {err && <p className="explain">{err}</p>}
      </div>
      <div className="editor-preview">
        <LivePreview data={data} />
      </div>
    </div>
  );
}

function QaPanel({ questionId }: { questionId: string }) {
  const [qa, setQa] = useState<QaPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    adminApi.qa(questionId).then(setQa).catch((e) => setErr(String(e.message)));
  }, [questionId]);
  if (err) return <p className="explain">{err}</p>;
  if (!qa) return <p>Yuklanmoqda...</p>;
  return (
    <div>
      <h2>Nashrdan oldingi tekshiruv (QA)</h2>
      <p><strong>{qa.all_passed ? "✓ Barcha tekshiruvlar o'tdi" : "✗ Tekshiruvlar to'liq emas"}</strong></p>
      <ul className="checklist">
        {qa.checklist.map((c) => (
          <li key={c.key} className={c.passed ? "pass" : "fail"}>
            {c.passed ? "✓" : "✗"} {c.detail}
          </li>
        ))}
      </ul>
      <h3>Mashq ko'rinishi</h3>
      <div className="preview">
        <p><strong>{qa.practice_preview.prompt}</strong></p>
        {qa.practice_preview.options.map((o) => (
          <div key={o.id}>
            <div className={"option" + (o.is_correct ? " correct" : "")}>{o.text}</div>
            <div className="explain">{o.explanation}</div>
          </div>
        ))}
        {qa.practice_preview.rules.map((r) => (
          <p key={r.code} className="muted">Qoida {r.code}{r.superseded ? " (eskirgan!)" : ""}: {r.text}</p>
        ))}
      </div>
      <h3>Imtihon ko'rinishi (javob ko'rsatilmaydi)</h3>
      <div className="preview">
        <p><strong>{qa.exam_preview.prompt}</strong></p>
        {qa.exam_preview.options.map((o) => <div key={o.id} className="option">{o.text}</div>)}
      </div>
    </div>
  );
}

function QuestionList({ onEdit, onQa }: { onEdit: (id: string) => void; onQa: (id: string) => void }) {
  const [items, setItems] = useState<AdminQuestionListItem[]>([]);
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => {
    const params: Record<string, string> = {};
    if (q) params.q = q;
    if (statusFilter) params.status = statusFilter;
    adminApi.listQuestions(params).then((r) => setItems(r.items)).catch((e) => setErr(String(e.message)));
  }, [q, statusFilter]);
  useEffect(load, [load]);
  return (
    <div>
      <h2>Savollar</h2>
      <input placeholder="Qidiruv (matn)" value={q} onChange={(e) => setQ(e.target.value)} />
      <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
        <option value="">Barcha holatlar</option>
        {STATUS_KEYS.map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
      </select>
      {err && <p className="explain">{err}</p>}
      {items.map((it) => (
        <div key={it.id} className="review-item">
          <p className="muted">{topicLabel(it.topic)} · <StatusBadge status={it.lifecycle_status} />{it.has_media ? " · media" : ""}</p>
          <p>{it.prompt || "(matnsiz)"}</p>
          <button className="secondary" onClick={() => onEdit(it.id)}>Tahrirlash</button>
          <button className="secondary" onClick={() => onQa(it.id)}>QA</button>
        </div>
      ))}
      {items.length === 0 && <p className="muted">Savollar topilmadi</p>}
    </div>
  );
}

function QuestionsSection({ canReview }: { canReview: boolean }) {
  const [view, setView] = useState<"list" | "editor" | "qa">("list");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [qaId, setQaId] = useState<string | null>(null);
  return (
    <div>
      <div className="admin-subnav">
        <button type="button" className={view === "list" ? "active" : ""} onClick={() => setView("list")}>Ro'yxat</button>
        <button type="button" className={view === "editor" ? "active" : ""} onClick={() => { setEditingId(null); setView("editor"); }}>Yangi savol</button>
        {qaId && <button type="button" className={view === "qa" ? "active" : ""} onClick={() => setView("qa")}>QA</button>}
      </div>
      {view === "list" && (
        <QuestionList
          onEdit={(id) => { setEditingId(id); setView("editor"); }}
          onQa={(id) => { setQaId(id); setView("qa"); }}
        />
      )}
      {view === "editor" && (
        <Editor editingId={editingId} canReview={canReview} onSaved={(_vid, qid) => { setQaId(qid); }} />
      )}
      {view === "qa" && qaId && <QaPanel questionId={qaId} />}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Reports queue (existing)
// --------------------------------------------------------------------------- //
function ReportsQueue() {
  const [reports, setReports] = useState<AdminReport[]>([]);
  const [statusFilter, setStatusFilter] = useState("open");
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => {
    adminApi.reports(statusFilter || undefined).then((r) => setReports(r.reports)).catch((e) => setErr(String(e.message)));
  }, [statusFilter]);
  useEffect(load, [load]);
  return (
    <div>
      <h2>Shikoyatlar navbati</h2>
      <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
        <option value="">Barchasi</option>
        <option value="open">Ochiq</option>
        <option value="triaged">Ko'rib chiqilmoqda</option>
        <option value="resolved">Hal qilingan</option>
        <option value="rejected">Rad etilgan</option>
      </select>
      {err && <p className="explain">{err}</p>}
      {reports.map((r) => (
        <div key={r.id} className="review-item">
          <p className="muted">{r.reason} · {r.status}</p>
          <p>{r.note || "(izohsiz)"}</p>
          <p className="muted">version: {r.question_version_id}</p>
          <button className="secondary" onClick={() => adminApi.resolveReport(r.id, "resolve").then(load)}>Hal qilindi</button>
          <button className="secondary" onClick={() => adminApi.resolveReport(r.id, "reject").then(load)}>Rad etish</button>
        </div>
      ))}
      {reports.length === 0 && <p className="muted">Shikoyatlar yo'q</p>}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Theory management (Nazariya): generic list + editor for catalogue entities
// --------------------------------------------------------------------------- //
type TheoryEntity = "signs" | "markings" | "gestures" | "lights";
type FieldKind = "text" | "textarea" | "select";
interface FieldDesc {
  key: string;
  label: string;
  kind: FieldKind;
  options?: { value: string; label: string }[];
}
interface TheoryRow {
  id: string;
  code?: string | null;
  name?: string;
  title?: string;
  family?: string;
  group?: string;
  kind?: string;
  slug?: string;
  media_url?: string | null;
  lifecycle_status: string;
  current_version_id: string | null;
  latest_version_id: string | null;
}
interface SavedRef {
  versionId: string;
  containerId: string;
}
interface TheoryEntityConfig {
  singular: string;
  createFields: FieldDesc[];
  contentFields: FieldDesc[];
  hasAnimation: boolean;
  list: (inc: boolean) => Promise<TheoryRow[]>;
  create: (payload: Record<string, unknown>) => Promise<SavedRef>;
  edit: (id: string, payload: Record<string, unknown>) => Promise<SavedRef>;
  submit: (vid: string) => Promise<TheoryVersionOut>;
  review: (vid: string) => Promise<TheoryVersionOut>;
  publish: (vid: string) => Promise<TheoryVersionOut>;
  loadContent: (row: TheoryRow) => Promise<Record<string, string> | null>;
  display: (row: TheoryRow) => string;
}

const SIGN_FAMILIES = [
  { value: "warning", label: "Ogohlantiruvchi" },
  { value: "priority", label: "Imtiyoz" },
  { value: "prohibitory", label: "Taqiqlovchi" },
  { value: "mandatory", label: "Buyuruvchi" },
  { value: "information", label: "Axborot-ko'rsatkich" },
  { value: "service", label: "Servis" },
  { value: "additional_plate", label: "Qo'shimcha" }
];
const MARKING_GROUPS = [
  { value: "horizontal", label: "Gorizontal" },
  { value: "vertical", label: "Vertikal" },
  { value: "temporary", label: "Vaqtinchalik" }
];
const LIGHT_KINDS = [
  { value: "main", label: "Asosiy" },
  { value: "arrow_section", label: "Strelka seksiyasi" },
  { value: "flashing", label: "Miltillovchi" },
  { value: "pedestrian", label: "Piyodalar" },
  { value: "railway", label: "Temir yo'l" },
  { value: "special", label: "Maxsus" }
];

function clean(s: string | null | undefined): string {
  return s == null ? "" : s;
}

const THEORY_CONFIGS: Record<TheoryEntity, TheoryEntityConfig> = {
  signs: {
    singular: "belgi",
    createFields: [
      { key: "official_code", label: "Rasmiy kod", kind: "text" },
      { key: "family", label: "Oila", kind: "select", options: SIGN_FAMILIES }
    ],
    contentFields: [
      { key: "name", label: "Nomi", kind: "text" },
      { key: "meaning", label: "Ma'nosi", kind: "textarea" },
      { key: "driver_action", label: "Haydovchi harakati", kind: "textarea" },
      { key: "important", label: "Muhim", kind: "textarea" },
      { key: "exam_trap", label: "Imtihon tuzog'i", kind: "textarea" },
      { key: "memory_tip", label: "Eslab qolish", kind: "textarea" },
      { key: "keywords", label: "Kalit so'zlar", kind: "text" }
    ],
    hasAnimation: false,
    list: (inc) => adminApi.theoryListSigns(undefined, inc).then((r) => r.signs as unknown as TheoryRow[]),
    create: (p) => adminApi.theoryCreateSign(p as unknown as SignCreateInput).then((r) => ({ versionId: r.id, containerId: r.road_sign_id })),
    edit: (id, p) => adminApi.theoryEditSign(id, p as unknown as SignContentInput).then((r) => ({ versionId: r.id, containerId: r.road_sign_id })),
    submit: (vid) => adminApi.theorySubmitSign(vid),
    review: (vid) => adminApi.theoryReviewSign(vid),
    publish: (vid) => adminApi.theoryPublishSign(vid),
    loadContent: async (row) => {
      if (row.lifecycle_status !== "published" || !row.code) return null;
      try {
        const d = await theoryApi.sign(row.code);
        return {
          name: clean(d.name), meaning: clean(d.meaning), driver_action: clean(d.driver_action),
          important: clean(d.important), exam_trap: clean(d.exam_trap), memory_tip: clean(d.memory_tip), keywords: ""
        };
      } catch {
        return null;
      }
    },
    display: (row) => row.name || ""
  },
  markings: {
    singular: "chiziq",
    createFields: [
      { key: "group", label: "Guruh", kind: "select", options: MARKING_GROUPS },
      { key: "code", label: "Kod", kind: "text" }
    ],
    contentFields: [
      { key: "name", label: "Nomi", kind: "text" },
      { key: "meaning", label: "Ma'nosi", kind: "textarea" },
      { key: "can_cross", label: "Kesib o'tish mumkinmi", kind: "textarea" },
      { key: "can_stop_park", label: "To'xtash / turish", kind: "textarea" },
      { key: "conflict_rule", label: "Ziddiyat qoidasi", kind: "textarea" },
      { key: "exam_trap", label: "Imtihon tuzog'i", kind: "textarea" },
      { key: "memory_tip", label: "Eslab qolish", kind: "textarea" },
      { key: "keywords", label: "Kalit so'zlar", kind: "text" }
    ],
    hasAnimation: false,
    list: (inc) => adminApi.theoryListMarkings(inc).then((r) => r.markings as unknown as TheoryRow[]),
    create: (p) => adminApi.theoryCreateMarking(p as unknown as MarkingCreateInput).then((r) => ({ versionId: r.id, containerId: r.road_marking_id })),
    edit: (id, p) => adminApi.theoryEditMarking(id, p as unknown as MarkingContentInput).then((r) => ({ versionId: r.id, containerId: r.road_marking_id })),
    submit: (vid) => adminApi.theorySubmitMarking(vid),
    review: (vid) => adminApi.theoryReviewMarking(vid),
    publish: (vid) => adminApi.theoryPublishMarking(vid),
    loadContent: async (row) => {
      if (row.lifecycle_status !== "published") return null;
      try {
        const d = await theoryApi.marking(row.id);
        return {
          name: clean(d.name), meaning: clean(d.meaning), can_cross: clean(d.can_cross),
          can_stop_park: clean(d.can_stop_park), conflict_rule: clean(d.conflict_rule),
          exam_trap: clean(d.exam_trap), memory_tip: clean(d.memory_tip), keywords: ""
        };
      } catch {
        return null;
      }
    },
    display: (row) => row.name || ""
  },
  gestures: {
    singular: "ishora",
    createFields: [{ key: "code", label: "Kod", kind: "text" }],
    contentFields: [
      { key: "name", label: "Nomi", kind: "text" },
      { key: "position_desc", label: "Holati tavsifi", kind: "textarea" },
      { key: "allowed", label: "Ruxsat etiladi", kind: "textarea" },
      { key: "forbidden", label: "Taqiqlanadi", kind: "textarea" },
      { key: "memory_tip", label: "Eslab qolish", kind: "textarea" },
      { key: "keywords", label: "Kalit so'zlar", kind: "text" }
    ],
    hasAnimation: true,
    list: (inc) => adminApi.theoryListGestures(inc).then((r) => r.gestures as unknown as TheoryRow[]),
    create: (p) => adminApi.theoryCreateGesture(p as unknown as GestureCreateInput).then((r) => ({ versionId: r.id, containerId: r.gesture_id })),
    edit: (id, p) => adminApi.theoryEditGesture(id, p as unknown as GestureContentInput).then((r) => ({ versionId: r.id, containerId: r.gesture_id })),
    submit: (vid) => adminApi.theorySubmitGesture(vid),
    review: (vid) => adminApi.theoryReviewGesture(vid),
    publish: (vid) => adminApi.theoryPublishGesture(vid),
    loadContent: async (row) => {
      if (row.lifecycle_status !== "published") return null;
      try {
        const d = await theoryApi.gesture(row.id);
        return {
          name: clean(d.name), position_desc: clean(d.position_desc), allowed: clean(d.allowed),
          forbidden: clean(d.forbidden), memory_tip: clean(d.memory_tip), keywords: ""
        };
      } catch {
        return null;
      }
    },
    display: (row) => row.name || ""
  },
  lights: {
    singular: "svetofor",
    createFields: [{ key: "kind", label: "Turi", kind: "select", options: LIGHT_KINDS }],
    contentFields: [
      { key: "title", label: "Sarlavha", kind: "text" },
      { key: "meaning", label: "Ma'nosi", kind: "textarea" },
      { key: "movement_permitted", label: "Harakat mumkinmi", kind: "textarea" },
      { key: "direction_permitted", label: "Yo'nalish", kind: "textarea" },
      { key: "exceptions", label: "Istisnolar", kind: "textarea" },
      { key: "typical_exam_situation", label: "Imtihon vaziyati", kind: "textarea" },
      { key: "keywords", label: "Kalit so'zlar", kind: "text" }
    ],
    hasAnimation: false,
    list: (inc) => adminApi.theoryListLights(inc).then((r) => r.lights as unknown as TheoryRow[]),
    create: (p) => adminApi.theoryCreateLight(p as unknown as LightCreateInput).then((r) => ({ versionId: r.id, containerId: r.light_id })),
    edit: (id, p) => adminApi.theoryEditLight(id, p as unknown as LightContentInput).then((r) => ({ versionId: r.id, containerId: r.light_id })),
    submit: (vid) => adminApi.theorySubmitLight(vid),
    review: (vid) => adminApi.theoryReviewLight(vid),
    publish: (vid) => adminApi.theoryPublishLight(vid),
    loadContent: async (row) => {
      if (row.lifecycle_status !== "published") return null;
      try {
        const d = await theoryApi.light(row.id);
        return {
          title: clean(d.title), meaning: clean(d.meaning), movement_permitted: clean(d.movement_permitted),
          direction_permitted: clean(d.direction_permitted), exceptions: clean(d.exceptions),
          typical_exam_situation: clean(d.typical_exam_situation), keywords: ""
        };
      } catch {
        return null;
      }
    },
    display: (row) => row.title || ""
  }
};

function initCreateVals(config: TheoryEntityConfig): Record<string, string> {
  const v: Record<string, string> = {};
  for (const f of config.createFields) v[f.key] = f.options ? f.options[0].value : "";
  return v;
}

function TheoryPreview({
  config,
  content,
  ruleCodes,
  row
}: {
  config: TheoryEntityConfig;
  content: Record<string, string>;
  ruleCodes: string[];
  row: TheoryRow | null;
}) {
  const title = content.name || content.title || row?.name || row?.title || "(nomi)";
  return (
    <div className="preview">
      <p><strong>{title}</strong></p>
      {config.contentFields.map((f) =>
        content[f.key] ? (
          <p key={f.key}><span className="muted">{f.label}: </span>{content[f.key]}</p>
        ) : null
      )}
      {ruleCodes.length > 0 && <p className="muted">Qoida: {ruleCodes.join(", ")}</p>}
    </div>
  );
}

function TheoryEditor({
  entity,
  config,
  row,
  canReview
}: {
  entity: TheoryEntity;
  config: TheoryEntityConfig;
  row: TheoryRow | null;
  canReview: boolean;
}) {
  const [createVals, setCreateVals] = useState<Record<string, string>>(() => initCreateVals(config));
  const [content, setContent] = useState<Record<string, string>>({});
  const [ruleCodes, setRuleCodes] = useState<string[]>([]);
  const [mediaId, setMediaId] = useState<string | null>(null);
  const [animMediaId, setAnimMediaId] = useState<string | null>(null);
  const [containerId, setContainerId] = useState<string | null>(row ? row.id : null);
  const [versionId, setVersionId] = useState<string | null>(null);
  const [statusNow, setStatusNow] = useState<string | null>(row ? row.lifecycle_status : null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!row) return;
    config.loadContent(row).then((c) => { if (c) setContent(c); }).catch(() => {});
  }, [row, config]);

  function buildCreatePayload(): Record<string, unknown> {
    const p: Record<string, unknown> = { ...createVals, media_id: mediaId };
    if (config.hasAnimation) p.animation_media_id = animMediaId;
    return p;
  }
  function buildContentPayload(): Record<string, unknown> {
    const p: Record<string, unknown> = { ...content, rule_codes: ruleCodes, media_id: mediaId, ai_assisted: false };
    if (config.hasAnimation) p.animation_media_id = animMediaId;
    if (entity === "signs") p.question_ids = [];
    return p;
  }

  async function save() {
    setErr(null);
    setMsg(null);
    try {
      let cid = containerId;
      if (!cid) {
        const created = await config.create(buildCreatePayload());
        cid = created.containerId;
        setContainerId(cid);
      }
      const saved = await config.edit(cid, buildContentPayload());
      setVersionId(saved.versionId);
      setStatusNow("draft");
      setMsg("Saqlandi (qoralama versiya yaratildi)");
    } catch (e) {
      setErr(String((e as Error).message));
    }
  }

  async function uploadMedia(file: File, target: "main" | "anim") {
    try {
      const m = await adminApi.uploadMedia(file);
      if (target === "anim") setAnimMediaId(m.id);
      else setMediaId(m.id);
      setMsg("Media yuklandi");
    } catch (e) {
      setErr(String((e as Error).message));
    }
  }

  async function transition(kind: "submit" | "review" | "publish") {
    if (!versionId) return;
    setErr(null);
    try {
      const fn = kind === "submit" ? config.submit : kind === "review" ? config.review : config.publish;
      const v = await fn(versionId);
      setStatusNow(v.status);
      setMsg(`Amal bajarildi: ${kind}`);
    } catch (e) {
      setErr(String((e as Error).message));
    }
  }

  return (
    <div className="editor-layout">
      <div className="editor-form">
        <h2>
          {row ? `${config.singular} tahriri` : `Yangi ${config.singular}`}{" "}
          {statusNow && <StatusBadge status={statusNow} />}
        </h2>
        {row && <p className="explain">Nashr etilgan kontent tahriri yangi versiya yaratadi. Media qayta biriktirilishi kerak.</p>}

        <h3>Asosiy</h3>
        {config.createFields.map((f) =>
          row ? (
            <p key={f.key} className="muted">{f.label}: {String((row as unknown as Record<string, unknown>)[f.key] ?? "—")}</p>
          ) : f.kind === "select" ? (
            <div key={f.key}>
              <label className="muted">{f.label}</label>
              <select value={createVals[f.key]} onChange={(e) => setCreateVals({ ...createVals, [f.key]: e.target.value })}>
                {f.options!.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          ) : (
            <div key={f.key}>
              <label className="muted">{f.label}</label>
              <input value={createVals[f.key]} onChange={(e) => setCreateVals({ ...createVals, [f.key]: e.target.value })} />
            </div>
          )
        )}

        <h3>Matn</h3>
        {config.contentFields.map((f) => (
          <div key={f.key}>
            <label className="muted">{f.label}</label>
            {f.kind === "textarea" ? (
              <textarea value={content[f.key] || ""} onChange={(e) => setContent({ ...content, [f.key]: e.target.value })} />
            ) : (
              <input value={content[f.key] || ""} onChange={(e) => setContent({ ...content, [f.key]: e.target.value })} />
            )}
          </div>
        ))}

        <RulePicker selected={ruleCodes} onChange={setRuleCodes} />

        <label className="muted">Media (rasm/gif/video)</label>
        <input type="file" onChange={(e) => e.target.files && e.target.files[0] && uploadMedia(e.target.files[0], "main")} />
        {mediaId && <p className="muted">media_id: {mediaId}</p>}
        {config.hasAnimation && (
          <>
            <label className="muted">Animatsiya media</label>
            <input type="file" onChange={(e) => e.target.files && e.target.files[0] && uploadMedia(e.target.files[0], "anim")} />
            {animMediaId && <p className="muted">animation_media_id: {animMediaId}</p>}
          </>
        )}

        <div style={{ height: 12 }} />
        <button onClick={save}>Saqlash</button>
        {versionId && (
          <div className="review-actions">
            <button className="secondary" onClick={() => transition("submit")}>Ko'rikka yuborish</button>
            {canReview && <button className="secondary" onClick={() => transition("review")}>Ko'rildi</button>}
            {canReview && <button onClick={() => transition("publish")}>Nashr etish</button>}
          </div>
        )}
        {msg && <p className="explain">{msg}</p>}
        {err && <p className="explain">{err}</p>}
      </div>
      <div className="editor-preview">
        <TheoryPreview config={config} content={content} ruleCodes={ruleCodes} row={row} />
      </div>
    </div>
  );
}

function TheoryList({
  config,
  onCreate,
  onEdit
}: {
  config: TheoryEntityConfig;
  onCreate: () => void;
  onEdit: (row: TheoryRow) => void;
}) {
  const [rows, setRows] = useState<TheoryRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => {
    config.list(true).then(setRows).catch((e) => setErr(String(e.message)));
  }, [config]);
  useEffect(load, [load]);
  return (
    <div>
      <div className="admin-nav">
        <button type="button" onClick={onCreate}>+ Yangi {config.singular}</button>
        <button type="button" className="secondary" onClick={load}>Yangilash</button>
      </div>
      {err && <p className="explain">{err}</p>}
      {rows.map((r) => (
        <div key={r.id} className="review-item">
          <p className="muted">
            {r.code || r.slug || r.id} · {r.family || r.group || r.kind || ""} <StatusBadge status={r.lifecycle_status} />
          </p>
          <p>{config.display(r) || "(nomsiz)"}</p>
          <button className="secondary" onClick={() => onEdit(r)}>Tahrirlash</button>
        </div>
      ))}
      {rows.length === 0 && <p className="muted">Element topilmadi</p>}
    </div>
  );
}

const BLOCK_TYPES: { id: import("./types").BlockType; label: string }[] = [
  { id: "text", label: "Matn" },
  { id: "rule_callout", label: "Qoida" },
  { id: "warning", label: "Ogohlantirish" },
  { id: "memory_tip", label: "Eslatma" },
  { id: "example", label: "Misol" },
  { id: "table", label: "Jadval" },
  { id: "practice_link", label: "Mashq havolasi" },
  { id: "image", label: "Rasm" },
  { id: "diagram", label: "Diagramma" }
];

function BlockEditor({ blocks, onChange }: { blocks: AdminBlockInput[]; onChange: (b: AdminBlockInput[]) => void }) {
  const add = (type: import("./types").BlockType) => onChange([...blocks, { type, body: "" }]);
  const patch = (i: number, p: Partial<AdminBlockInput>) => onChange(blocks.map((b, j) => (j === i ? { ...b, ...p } : b)));
  const remove = (i: number) => onChange(blocks.filter((_, j) => j !== i));
  const move = (i: number, d: number) => {
    const j = i + d;
    if (j < 0 || j >= blocks.length) return;
    const c = [...blocks];
    [c[i], c[j]] = [c[j], c[i]];
    onChange(c);
  };
  async function upload(i: number, file: File) {
    try {
      const m = await adminApi.uploadMedia(file);
      patch(i, { media_id: m.id });
    } catch {
      /* surfaced by caller flows */
    }
  }
  const isMedia = (t: string) => t === "image" || t === "diagram" || t === "animation";
  return (
    <div className="block-editor">
      <div className="block-add">
        {BLOCK_TYPES.map((t) => (
          <button key={t.id} type="button" className="secondary" onClick={() => add(t.id)}>+ {t.label}</button>
        ))}
      </div>
      {blocks.map((b, i) => (
        <div key={i} className="review-item block-row">
          <div className="block-head">
            <strong>{BLOCK_TYPES.find((t) => t.id === b.type)?.label || b.type}</strong>
            <span>
              <button type="button" className="secondary" onClick={() => move(i, -1)}>↑</button>
              <button type="button" className="secondary" onClick={() => move(i, 1)}>↓</button>
              <button type="button" className="secondary" onClick={() => remove(i)}>o'chirish</button>
            </span>
          </div>
          {isMedia(b.type) ? (
            <div>
              <input type="file" onChange={(e) => e.target.files && e.target.files[0] && upload(i, e.target.files[0])} />
              {b.media_id && <p className="muted">media_id: {b.media_id}</p>}
              <input placeholder="Izoh (ixtiyoriy)" value={b.body || ""} onChange={(e) => patch(i, { body: e.target.value })} />
            </div>
          ) : b.type === "table" ? (
            <textarea placeholder={'JSON: {"headers":["A","B"],"rows":[["1","2"]]}'} value={b.body || ""} onChange={(e) => patch(i, { body: e.target.value })} />
          ) : (
            <textarea placeholder="Matn" value={b.body || ""} onChange={(e) => patch(i, { body: e.target.value })} />
          )}
          {b.type === "rule_callout" && (
            <input placeholder="Qoida kodi (masalan 6.13)" value={b.rule_code || ""} onChange={(e) => patch(i, { rule_code: e.target.value })} />
          )}
        </div>
      ))}
      {blocks.length === 0 && <p className="muted">Blok qo'shing.</p>}
    </div>
  );
}

function SectionsManager({ canReview }: { canReview: boolean }) {
  const [rows, setRows] = useState<TheoryRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [topic, setTopic] = useState("");
  const [position, setPosition] = useState(0);
  const load = useCallback(() => {
    adminApi.theoryListSections(true).then((r) => setRows(r.sections as unknown as TheoryRow[])).catch((e) => setErr(String(e.message)));
  }, []);
  useEffect(load, [load]);
  async function create() {
    setErr(null); setMsg(null);
    try {
      await adminApi.theoryCreateSection({ slug, title, subtitle, topic: topic || null, position });
      setMsg("Bo'lim yaratildi"); setSlug(""); setTitle(""); setSubtitle(""); load();
    } catch (e) { setErr(String((e as Error).message)); }
  }
  async function publish(id: string) {
    setErr(null);
    try { await adminApi.theoryPublishSection(id); setMsg("Nashr etildi"); load(); }
    catch (e) { setErr(String((e as Error).message)); }
  }
  return (
    <div>
      <h3>Yangi bo'lim</h3>
      <label className="muted">Slug</label>
      <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="masalan: tezlik" />
      <label className="muted">Sarlavha</label>
      <input value={title} onChange={(e) => setTitle(e.target.value)} />
      <label className="muted">Tavsif</label>
      <input value={subtitle} onChange={(e) => setSubtitle(e.target.value)} />
      <label className="muted">Mavzu (ixtiyoriy)</label>
      <select value={topic} onChange={(e) => setTopic(e.target.value)}>
        <option value="">—</option>
        {TOPIC_KEYS.map((t) => <option key={t} value={t}>{topicLabel(t)}</option>)}
      </select>
      <label className="muted">Tartib</label>
      <input type="number" value={position} onChange={(e) => setPosition(Number(e.target.value))} />
      <div style={{ height: 8 }} />
      <button disabled={!slug || !title} onClick={create}>Yaratish</button>
      {msg && <p className="explain">{msg}</p>}
      {err && <p className="explain">{err}</p>}
      <h3>Bo'limlar</h3>
      {rows.map((r) => (
        <div key={r.id} className="review-item">
          <p className="muted">{r.slug || r.id} <StatusBadge status={r.lifecycle_status} /></p>
          <p>{r.title || "(nomsiz)"}</p>
          {canReview && r.lifecycle_status !== "published" && (
            <button className="secondary" onClick={() => publish(r.id)}>Nashr etish</button>
          )}
        </div>
      ))}
      {rows.length === 0 && <p className="muted">Bo'limlar yo'q</p>}
    </div>
  );
}

function ArticlesManager({ canReview }: { canReview: boolean }) {
  const [articles, setArticles] = useState<TheoryRow[]>([]);
  const [sections, setSections] = useState<TheoryRow[]>([]);
  const [mode, setMode] = useState<"list" | "edit">("list");
  const [articleId, setArticleId] = useState<string | null>(null);
  const [versionId, setVersionId] = useState<string | null>(null);
  const [statusNow, setStatusNow] = useState<string | null>(null);
  const [secId, setSecId] = useState("");
  const [slug, setSlug] = useState("");
  const [kind, setKind] = useState("lesson");
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [aiA, setAiA] = useState(true);
  const [blocks, setBlocks] = useState<AdminBlockInput[]>([]);
  const [ruleCodes, setRuleCodes] = useState<string[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    adminApi.theoryListArticles(undefined, true).then((r) => setArticles(r.articles as unknown as TheoryRow[])).catch((e) => setErr(String(e.message)));
  }, []);
  useEffect(() => {
    load();
    adminApi.theoryListSections(true).then((r) => {
      const s = r.sections as unknown as TheoryRow[];
      setSections(s);
      if (s[0]) setSecId(s[0].id);
    }).catch(() => undefined);
  }, [load]);

  function resetContent() { setTitle(""); setSummary(""); setAiA(true); setBlocks([]); setRuleCodes([]); }

  async function createArticle() {
    setErr(null); setMsg(null);
    try {
      const r = await adminApi.theoryCreateArticle({ section_id: secId, slug, kind: kind as "lesson" | "reference" | "quick_ref" | "common_mistake" });
      setArticleId(r.article_id); setVersionId(r.id); setStatusNow(r.status); resetContent(); setMode("edit");
      setMsg("Maqola yaratildi — mazmun qo'shing.");
    } catch (e) { setErr(String((e as Error).message)); }
  }

  function buildBlocks(): AdminBlockInput[] {
    return blocks.map((b) => {
      if (b.type === "table") {
        let data: Record<string, unknown> | null = null;
        try { data = JSON.parse(b.body || "{}"); } catch { data = null; }
        return { type: b.type, body: "", data };
      }
      return b;
    });
  }

  async function saveContent() {
    if (!articleId) return;
    setErr(null); setMsg(null);
    try {
      const r = await adminApi.theoryEditArticle(articleId, { title, summary, ai_assisted: aiA, blocks: buildBlocks(), rule_codes: ruleCodes, question_ids: [] });
      setVersionId(r.id); setStatusNow(r.status); setMsg(`Saqlandi (v${r.version}, ${r.status})`); load();
    } catch (e) { setErr(String((e as Error).message)); }
  }

  async function transition(k: "submit" | "review" | "publish") {
    if (!versionId) return;
    setErr(null);
    try {
      const fn = k === "submit" ? adminApi.theorySubmitArticle : k === "review" ? adminApi.theoryReviewArticle : adminApi.theoryPublishArticle;
      const r = await fn(versionId);
      setStatusNow(r.status); setMsg(`Amal: ${k} → ${r.status}`); load();
    } catch (e) { setErr(String((e as Error).message)); }
  }

  if (mode === "edit") {
    return (
      <div>
        <button type="button" className="secondary" onClick={() => { setMode("list"); setArticleId(null); setVersionId(null); }}>← Ro'yxat</button>
        <h3>Maqola mazmuni {statusNow && <StatusBadge status={statusNow} />}</h3>
        <p className="explain">Mavjud maqolani tahrirlash yangi versiya yaratadi. Joriy mazmun oldindan yuklanmaydi — yangi versiya bloklarini kiriting.</p>
        <label className="muted">Sarlavha</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
        <label className="muted">Qisqa mazmun</label>
        <textarea value={summary} onChange={(e) => setSummary(e.target.value)} />
        <label><input type="checkbox" checked={aiA} onChange={(e) => setAiA(e.target.checked)} /> AI yordamida (tekshirilishi kerak)</label>
        <h4>Bloklar</h4>
        <BlockEditor blocks={blocks} onChange={setBlocks} />
        <RulePicker selected={ruleCodes} onChange={setRuleCodes} />
        <div style={{ height: 12 }} />
        <button onClick={saveContent}>Mazmunni saqlash</button>
        {versionId && (
          <div className="review-actions">
            <button className="secondary" onClick={() => transition("submit")}>Ko'rikka yuborish</button>
            {canReview && <button className="secondary" onClick={() => transition("review")}>Ko'rildi</button>}
            {canReview && <button onClick={() => transition("publish")}>Nashr etish</button>}
          </div>
        )}
        {msg && <p className="explain">{msg}</p>}
        {err && <p className="explain">{err}</p>}
      </div>
    );
  }
  return (
    <div>
      <h3>Yangi maqola</h3>
      <label className="muted">Bo'lim</label>
      <select value={secId} onChange={(e) => setSecId(e.target.value)}>
        {sections.map((s) => <option key={s.id} value={s.id}>{s.title || s.slug || s.id}</option>)}
      </select>
      <label className="muted">Slug</label>
      <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="masalan: tezlik-asoslari" />
      <label className="muted">Tur</label>
      <select value={kind} onChange={(e) => setKind(e.target.value)}>
        <option value="lesson">Dars</option>
        <option value="reference">Ma'lumotnoma</option>
        <option value="quick_ref">Tez ma'lumot</option>
        <option value="common_mistake">Ko'p uchraydigan xato</option>
      </select>
      <div style={{ height: 8 }} />
      <button disabled={!secId || !slug} onClick={createArticle}>Yaratish</button>
      {err && <p className="explain">{err}</p>}
      <h3>Maqolalar</h3>
      {articles.map((a) => (
        <div key={a.id} className="review-item">
          <p className="muted">{a.slug || a.id} <StatusBadge status={a.lifecycle_status} /></p>
          <p>{a.title || "(nomsiz)"}</p>
          <button className="secondary" onClick={() => { setArticleId(a.id); setVersionId(null); setStatusNow(a.lifecycle_status); resetContent(); setMode("edit"); }}>Yangi versiya / tahrirlash</button>
        </div>
      ))}
      {articles.length === 0 && <p className="muted">Maqolalar yo'q</p>}
    </div>
  );
}

const THEORY_TABS: { id: string; label: string }[] = [
  { id: "sections", label: "Bo'limlar" },
  { id: "articles", label: "Maqolalar" },
  { id: "signs", label: "Belgilar" },
  { id: "markings", label: "Chiziqlar" },
  { id: "gestures", label: "Ishoralar" },
  { id: "lights", label: "Svetofor" }
];

function isEditableEntity(s: string): s is TheoryEntity {
  return s === "signs" || s === "markings" || s === "gestures" || s === "lights";
}

function TheorySection({ canReview }: { canReview: boolean }) {
  const [sub, setSub] = useState<string>("signs");
  const [editing, setEditing] = useState<{ entity: TheoryEntity; row: TheoryRow | null } | null>(null);
  return (
    <div>
      <div className="admin-subnav">
        {THEORY_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={sub === t.id ? "active" : ""}
            onClick={() => { setSub(t.id); setEditing(null); }}
          >
            {t.label}
          </button>
        ))}
      </div>
      {sub === "sections" && <SectionsManager canReview={canReview} />}
      {sub === "articles" && <ArticlesManager canReview={canReview} />}
      {isEditableEntity(sub) && !editing && (
        <TheoryList
          config={THEORY_CONFIGS[sub]}
          onCreate={() => setEditing({ entity: sub, row: null })}
          onEdit={(row) => setEditing({ entity: sub, row })}
        />
      )}
      {editing && (
        <div>
          <button type="button" className="secondary" onClick={() => setEditing(null)}>← Ro'yxatga qaytish</button>
          <TheoryEditor
            key={editing.entity + (editing.row?.id || "new")}
            entity={editing.entity}
            config={THEORY_CONFIGS[editing.entity]}
            row={editing.row}
            canReview={canReview}
          />
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Review queue (theory versions flagged for review)
// --------------------------------------------------------------------------- //
const REVIEW_FNS: Partial<Record<keyof ReviewQueueOut, {
  review: (v: string) => Promise<TheoryVersionOut>;
  publish: (v: string) => Promise<TheoryVersionOut>;
}>> = {
  signs: { review: adminApi.theoryReviewSign, publish: adminApi.theoryPublishSign },
  markings: { review: adminApi.theoryReviewMarking, publish: adminApi.theoryPublishMarking },
  gestures: { review: adminApi.theoryReviewGesture, publish: adminApi.theoryPublishGesture },
  lights: { review: adminApi.theoryReviewLight, publish: adminApi.theoryPublishLight }
};

const REVIEW_GROUPS: { key: keyof ReviewQueueOut; label: string }[] = [
  { key: "articles", label: "Maqolalar" },
  { key: "signs", label: "Belgilar" },
  { key: "markings", label: "Chiziqlar" },
  { key: "gestures", label: "Ishoralar" },
  { key: "lights", label: "Svetofor" }
];

function ReviewQueue({ canReview }: { canReview: boolean }) {
  const [q, setQ] = useState<ReviewQueueOut | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(() => {
    adminApi.theoryReviewQueue().then(setQ).catch((e) => setErr(String(e.message)));
  }, []);
  useEffect(load, [load]);

  async function act(group: keyof ReviewQueueOut, vid: string, kind: "review" | "publish") {
    const fns = REVIEW_FNS[group];
    if (!fns) return;
    setErr(null);
    setMsg(null);
    try {
      await (kind === "review" ? fns.review(vid) : fns.publish(vid));
      setMsg("Amal bajarildi");
      load();
    } catch (e) {
      setErr(String((e as Error).message));
    }
  }

  if (err && !q) return <p className="explain">{err}</p>;
  if (!q) return <p>Yuklanmoqda...</p>;
  const total = REVIEW_GROUPS.reduce((s, g) => s + q[g.key].length, 0);
  return (
    <div>
      <h2>Ko'rik navbati</h2>
      {msg && <p className="explain">{msg}</p>}
      {err && <p className="explain">{err}</p>}
      {total === 0 && <p className="muted">Navbat bo'sh</p>}
      {REVIEW_GROUPS.map((g) =>
        q[g.key].length > 0 ? (
          <div key={g.key}>
            <h3>{g.label} ({q[g.key].length})</h3>
            {q[g.key].map((row) => (
              <div key={row.version_id} className="review-item">
                <p className="muted">versiya {row.version} · <StatusBadge status={row.status} /></p>
                <p className="muted">id: {row.container_id}</p>
                {canReview && REVIEW_FNS[g.key] && (
                  <div className="review-actions">
                    <button className="secondary" onClick={() => act(g.key, row.version_id, "review")}>Ko'rildi</button>
                    <button onClick={() => act(g.key, row.version_id, "publish")}>Nashr etish</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : null
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Root: grouped, role-aware navigation
// --------------------------------------------------------------------------- //
type AdminGroup = "dashboard" | "questions" | "theory" | "review" | "reports";

export function AdminArea({ role, onExit }: { role: string | null; onExit: () => void }) {
  const [group, setGroup] = useState<AdminGroup>("dashboard");
  const canReview = useMemo(
    () => role === "content_reviewer" || role === "admin" || role === "superadmin",
    [role]
  );
  const groups: { id: AdminGroup; label: string; show: boolean }[] = [
    { id: "dashboard", label: "Panel", show: true },
    { id: "questions", label: "Savollar", show: true },
    { id: "theory", label: "Nazariya", show: true },
    { id: "review", label: "Ko'rik navbati", show: canReview },
    { id: "reports", label: "Shikoyatlar", show: true }
  ];

  return (
    <div className="card admin">
      <button className="secondary" onClick={onExit}>Bosh sahifaga qaytish</button>
      <div className="admin-nav">
        {groups.filter((g) => g.show).map((g) => (
          <button key={g.id} className={group === g.id ? "active" : ""} onClick={() => setGroup(g.id)}>{g.label}</button>
        ))}
      </div>
      {group === "dashboard" && (
        <Dashboard onGoReports={() => setGroup("reports")} onGoReview={() => setGroup(canReview ? "review" : "reports")} />
      )}
      {group === "questions" && <QuestionsSection canReview={canReview} />}
      {group === "theory" && <TheorySection canReview={canReview} />}
      {group === "review" && canReview && <ReviewQueue canReview={canReview} />}
      {group === "reports" && <ReportsQueue />}
    </div>
  );
}
