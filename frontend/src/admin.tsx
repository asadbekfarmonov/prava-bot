// Admin studio (Uzbek). Security is enforced SERVER-SIDE on every endpoint; the UI
// role-gate is only a convenience. All author content is rendered as TEXT (React text
// nodes, auto-escaped) — auto-escaped React children only; raw HTML injection is never used (docs/spec/09 XSS).
import { useCallback, useEffect, useMemo, useState } from "react";
import { adminApi } from "./api";
import type {
  AdminOverview,
  AdminQuestionInput,
  AdminQuestionListItem,
  AdminReport,
  AdminRuleOut,
  QaPayload
} from "./types";

const TOPICS = [
  "general_rules", "road_signs", "road_markings", "signals", "intersections",
  "manoeuvring", "speed_distance", "overtaking", "stopping_parking", "vulnerable_users",
  "railway_crossings", "motorways_special", "vehicle_condition",
  "transport_of_people_cargo", "emergencies_first_aid"
];

const STATUSES = [
  "draft", "needs_review", "reviewed", "published",
  "needs_reverification", "superseded", "archived"
];

type Tab = "dashboard" | "list" | "editor" | "qa" | "reports";
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

function Dashboard() {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    adminApi.overview().then(setData).catch((e) => setErr(String(e.message)));
  }, []);
  if (err) return <p className="explain">{err}</p>;
  if (!data) return <p>Yuklanmoqda...</p>;
  return (
    <div>
      <h2>Boshqaruv paneli</h2>
      <div className="admin-grid">
        {Object.entries(data.counts).map(([k, v]) => (
          <div key={k} className="admin-stat">
            <div className="admin-stat-value">{v}</div>
            <div className="muted">{k}</div>
          </div>
        ))}
      </div>
      <h3>Ochiq shikoyatlar: {data.open_reports}</h3>
      <h3>Media: {data.media_storage.object_count} ta obyekt</h3>
      <h3>Mavzu qamrovi</h3>
      <ul>
        {Object.entries(data.topic_coverage).map(([topic, n]) => (
          <li key={topic} className="muted">{topic}: {n}</li>
        ))}
      </ul>
    </div>
  );
}

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
          {TOPICS.map((tp) => <option key={tp} value={tp}>{tp}</option>)}
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
        <option value="open">open</option>
        <option value="triaged">triaged</option>
        <option value="resolved">resolved</option>
        <option value="rejected">rejected</option>
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
        {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      {err && <p className="explain">{err}</p>}
      {items.map((it) => (
        <div key={it.id} className="review-item">
          <p className="muted">{it.topic} · {it.lifecycle_status}{it.has_media ? " · media" : ""}</p>
          <p>{it.prompt || "(matnsiz)"}</p>
          <button className="secondary" onClick={() => onEdit(it.id)}>Tahrirlash</button>
          <button className="secondary" onClick={() => onQa(it.id)}>QA</button>
        </div>
      ))}
      {items.length === 0 && <p className="muted">Savollar topilmadi</p>}
    </div>
  );
}

export function AdminArea({ role, onExit }: { role: string | null; onExit: () => void }) {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [qaId, setQaId] = useState<string | null>(null);
  const canReview = useMemo(
    () => role === "content_reviewer" || role === "admin" || role === "superadmin",
    [role]
  );

  return (
    <div className="card admin">
      <button className="secondary" onClick={onExit}>Bosh sahifaga qaytish</button>
      <div className="admin-nav">
        <button className={tab === "dashboard" ? "active" : ""} onClick={() => setTab("dashboard")}>Panel</button>
        <button className={tab === "list" ? "active" : ""} onClick={() => setTab("list")}>Savollar</button>
        <button className={tab === "editor" ? "active" : ""} onClick={() => { setEditingId(null); setTab("editor"); }}>Yangi</button>
        <button className={tab === "reports" ? "active" : ""} onClick={() => setTab("reports")}>Shikoyatlar</button>
      </div>
      {tab === "dashboard" && <Dashboard />}
      {tab === "list" && (
        <QuestionList
          onEdit={(id) => { setEditingId(id); setTab("editor"); }}
          onQa={(id) => { setQaId(id); setTab("qa"); }}
        />
      )}
      {tab === "editor" && (
        <Editor
          editingId={editingId}
          canReview={canReview}
          onSaved={(_vid, qid) => { setQaId(qid); }}
        />
      )}
      {tab === "qa" && qaId && <QaPanel questionId={qaId} />}
      {tab === "reports" && <ReportsQueue />}
    </div>
  );
}
