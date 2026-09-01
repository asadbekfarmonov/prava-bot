import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { api } from "./api";
import { getTelegramInitData, readyTelegram } from "./telegram";
import { t } from "./i18n/uz";
import type { AnswerResult, NextQuestion, ProfileOut, UserOut } from "./types";

const TOPICS = [
  "general_rules", "road_signs", "road_markings", "signals", "intersections",
  "manoeuvring", "speed_distance", "overtaking", "stopping_parking", "vulnerable_users",
  "railway_crossings", "motorways_special", "vehicle_condition",
  "transport_of_people_cargo", "emergencies_first_aid"
];

function Login({ onLogin }: { onLogin: (u: UserOut) => void }) {
  const [devAvailable, setDevAvailable] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const initData = getTelegramInitData();
    if (initData) {
      api.telegramLogin(initData).then((r) => onLogin(r.user)).catch((e) => setError(String(e.message)));
    }
    api.devConfig().then((c) => setDevAvailable(c.dev_auth_enabled)).catch(() => undefined);
  }, [onLogin]);

  return (
    <div className="card">
      <h1>{t("appTitle")}</h1>
      <p className="muted">{t("tagline")}</p>
      {error && <p className="explain">{t("openFromTelegram")}</p>}
      {devAvailable && (
        <button className="secondary" onClick={() => api.devLogin().then((r) => onLogin(r.user)).catch((e) => setError(String(e.message)))}>
          {t("devLogin")}
        </button>
      )}
    </div>
  );
}

function Onboarding({ onDone }: { onDone: (p: ProfileOut) => void }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="card">
      <h1>{t("onboardingTitle")}</h1>
      <label className="muted">{t("displayName")}</label>
      <input value={name} onChange={(e) => setName(e.target.value)} />
      <div style={{ height: 12 }} />
      <button
        disabled={busy || name.trim().length === 0}
        onClick={() => {
          setBusy(true);
          api.saveProfile(name.trim()).then((r) => onDone(r.profile)).finally(() => setBusy(false));
        }}
      >
        {t("save")}
      </button>
    </div>
  );
}

function Practice() {
  const [topic, setTopic] = useState<string>("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState<NextQuestion | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const topicArg = useMemo(() => (topic === "" ? null : topic), [topic]);

  async function start() {
    setError(null);
    setLoading(true);
    try {
      const s = await api.createSession(topicArg);
      setSessionId(s.id);
      await loadNext(s.id);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setLoading(false);
    }
  }

  async function loadNext(sid: string | null = sessionId) {
    setResult(null);
    setSelected(null);
    setError(null);
    try {
      const q = await api.nextQuestion(topicArg);
      setQuestion(q);
      void sid;
    } catch (e) {
      setQuestion(null);
      setError(String((e as Error).message));
    }
  }

  async function submit() {
    if (!sessionId || !question || !selected) return;
    setLoading(true);
    try {
      const r = await api.submitAnswer(sessionId, question.question_id, selected);
      setResult(r);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setLoading(false);
    }
  }

  if (!sessionId) {
    return (
      <div className="card">
        <h1>{t("startPractice")}</h1>
        <select value={topic} onChange={(e) => setTopic(e.target.value)}>
          <option value="">{t("topicAll")}</option>
          {TOPICS.map((tp) => (
            <option key={tp} value={tp}>{tp}</option>
          ))}
        </select>
        <button onClick={start} disabled={loading}>{t("startPractice")}</button>
        {error && <p className="explain">{error}</p>}
      </div>
    );
  }

  if (!question) {
    return <div className="card"><p>{error || t("noQuestions")}</p></div>;
  }

  return (
    <div className="card">
      <p className="muted">{question.topic}</p>
      <h1>{question.prompt}</h1>
      {question.options.map((o) => {
        let cls = "option";
        if (result) {
          if (o.id === result.correct_option_id) cls += " correct";
          else if (o.id === selected) cls += " wrong";
        } else if (o.id === selected) {
          cls += " selected";
        }
        const graded = result?.options.find((g) => g.id === o.id);
        return (
          <div key={o.id}>
            <button className={cls} disabled={!!result} onClick={() => setSelected(o.id)}>
              {o.text}
            </button>
            {graded && <div className="explain">{graded.explanation}</div>}
          </div>
        );
      })}

      {!result ? (
        <button onClick={submit} disabled={!selected || loading}>{t("submit")}</button>
      ) : (
        <div>
          <p><strong>{result.is_correct ? t("correct") : t("incorrect")}</strong></p>
          {result.short_explanation && (
            <p className="explain">{t("rememberThis")}: {result.short_explanation}</p>
          )}
          {result.rule && (
            <div className="rule">
              <strong>{t("rule")}: {result.rule.code}</strong>
              <p className="explain">{result.rule.text}</p>
            </div>
          )}
          <div style={{ height: 12 }} />
          <button onClick={() => loadNext()}>{t("next")}</button>
        </div>
      )}
      {error && <p className="explain">{error}</p>}
    </div>
  );
}

function App() {
  const [user, setUser] = useState<UserOut | null>(null);
  const [onboarded, setOnboarded] = useState(false);

  useEffect(() => {
    readyTelegram();
    api.me().then((r) => {
      setUser(r.user);
      setOnboarded(!!r.profile?.onboarding_completed);
    }).catch(() => undefined);
  }, []);

  if (!user) return <Login onLogin={(u) => { setUser(u); setOnboarded(u.onboarding_completed); }} />;
  if (!onboarded) return <Onboarding onDone={() => setOnboarded(true)} />;
  return <Practice />;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
