import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { api } from "./api";
import { getTelegramInitData, readyTelegram } from "./telegram";
import { t } from "./i18n/uz";
import type {
  AnswerResult,
  MockAttemptState,
  MockReview,
  NextQuestion,
  ProfileOut,
  UserOut
} from "./types";

const TOPICS = [
  "general_rules", "road_signs", "road_markings", "signals", "intersections",
  "manoeuvring", "speed_distance", "overtaking", "stopping_parking", "vulnerable_users",
  "railway_crossings", "motorways_special", "vehicle_condition",
  "transport_of_people_cargo", "emergencies_first_aid"
];

function fmtTime(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

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

function Practice({ onExit }: { onExit: () => void }) {
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
        <button className="secondary" onClick={onExit}>{t("backHome")}</button>
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

type LocalAnswer = { selected: string | null; marked: boolean };

function MockReviewView({ review, onExit }: { review: MockReview; onExit: () => void }) {
  return (
    <div className="card exam">
      <button className="secondary" onClick={onExit}>{t("backHome")}</button>
      <h1>{t("reviewAnswers")}</h1>
      {review.items.map((item) => (
        <div key={item.question_version_id} className="review-item">
          <p className="muted">{t("question")} {item.position} / {review.question_count}</p>
          <p><strong>{item.prompt}</strong></p>
          {item.options.map((o) => {
            let cls = "option";
            if (o.id === item.correct_option_id) cls += " correct";
            else if (o.id === item.selected_option_id) cls += " wrong";
            return (
              <div key={o.id}>
                <div className={cls}>{o.text}</div>
                <div className="explain">{o.explanation}</div>
              </div>
            );
          })}
          {item.short_explanation && (
            <p className="explain">{t("rememberThis")}: {item.short_explanation}</p>
          )}
          {item.rule && (
            <div className="rule">
              <strong>{t("rule")}: {item.rule.code}</strong>
              <p className="explain">{item.rule.text}</p>
            </div>
          )}
        </div>
      ))}
      <button className="secondary" onClick={onExit}>{t("backHome")}</button>
    </div>
  );
}

function MockResultView({
  attempt,
  onReview,
  onExit
}: {
  attempt: MockAttemptState;
  onReview: () => void;
  onExit: () => void;
}) {
  const r = attempt.result;
  return (
    <div className="card exam">
      <h1>{t("yourResult")}</h1>
      <p className="result-score">
        {attempt.correct_count} / {attempt.question_count} —{" "}
        <strong className={attempt.passed ? "pass" : "fail"}>
          {attempt.passed ? t("passed") : t("failed")}
        </strong>
      </p>
      {r && r.avg_answer_time_seconds != null && (
        <p className="muted">{t("avgAnswerTime")}: {Math.round(r.avg_answer_time_seconds)} s</p>
      )}
      {r && r.missed.length > 0 && (
        <div>
          <p><strong>{t("missedQuestions")}:</strong></p>
          <ul>
            {r.missed.map((m) => (
              <li key={m.question_version_id} className="explain">
                {m.position}-{t("question").toLowerCase()} · {m.topic}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div style={{ height: 12 }} />
      <button onClick={onReview}>{t("reviewAnswers")}</button>
      <div style={{ height: 8 }} />
      <button className="secondary" onClick={onExit}>{t("backHome")}</button>
    </div>
  );
}

function ExamMode({ onExit }: { onExit: () => void }) {
  const [attempt, setAttempt] = useState<MockAttemptState | null>(null);
  const [review, setReview] = useState<MockReview | null>(null);
  const [answers, setAnswers] = useState<Record<string, LocalAnswer>>({});
  const [index, setIndex] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const [confirming, setConfirming] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAttempt = useCallback((a: MockAttemptState) => {
    setAttempt(a);
    setRemaining(a.remaining_seconds);
    const map: Record<string, LocalAnswer> = {};
    for (const q of a.questions) {
      map[q.question_version_id] = {
        selected: q.selected_option_id,
        marked: q.marked_for_review
      };
    }
    setAnswers(map);
  }, []);

  async function begin() {
    setBusy(true);
    setError(null);
    try {
      let a: MockAttemptState | null = null;
      try {
        a = await api.currentMock();
      } catch {
        a = null;
      }
      if (!a || a.status !== "in_progress") {
        a = await api.startMock();
      }
      loadAttempt(a);
      setConfirming(false);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }

  const submit = useCallback(async () => {
    if (!attempt) return;
    setBusy(true);
    try {
      const done = await api.submitMock(attempt.id);
      setAttempt(done);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }, [attempt]);

  // Continuous countdown derived from the server-authoritative remaining time.
  useEffect(() => {
    if (!attempt || attempt.status !== "in_progress" || confirming) return;
    if (remaining <= 0) {
      void submit();
      return;
    }
    const id = window.setTimeout(() => setRemaining((x) => x - 1), 1000);
    return () => window.clearTimeout(id);
  }, [attempt, confirming, remaining, submit]);

  async function choose(qvid: string, optionId: string) {
    const prev = answers[qvid] || { selected: null, marked: false };
    const next = { selected: optionId, marked: prev.marked };
    setAnswers((m) => ({ ...m, [qvid]: next }));
    try {
      await api.saveMockAnswer(attempt!.id, qvid, optionId, next.marked);
    } catch (e) {
      setError(String((e as Error).message));
    }
  }

  async function toggleMark(qvid: string) {
    const prev = answers[qvid] || { selected: null, marked: false };
    const next = { selected: prev.selected, marked: !prev.marked };
    setAnswers((m) => ({ ...m, [qvid]: next }));
    try {
      await api.saveMockAnswer(attempt!.id, qvid, next.selected, next.marked);
    } catch (e) {
      setError(String((e as Error).message));
    }
  }

  if (confirming) {
    return (
      <div className="card exam">
        <button className="secondary" onClick={onExit}>{t("backHome")}</button>
        <h1>{t("mockMode")}</h1>
        <p className="explain">{t("examModeIntro")}</p>
        {error && <p className="explain">{error}</p>}
        <button onClick={begin} disabled={busy}>{t("examBegin")}</button>
      </div>
    );
  }

  if (!attempt) {
    return <div className="card exam"><p>{error || t("loading")}</p></div>;
  }

  if (review) {
    return <MockReviewView review={review} onExit={onExit} />;
  }

  if (attempt.status !== "in_progress") {
    return (
      <MockResultView
        attempt={attempt}
        onReview={async () => {
          try {
            const rv = await api.reviewMock(attempt.id);
            setReview(rv);
          } catch (e) {
            setError(String((e as Error).message));
          }
        }}
        onExit={onExit}
      />
    );
  }

  const questions = attempt.questions;
  const current = questions[index];
  const currentAnswer = current ? answers[current.question_version_id] : undefined;

  return (
    <div className="card exam">
      <div className="exam-bar">
        <span>{t("question")} {current.position} / {attempt.question_count}</span>
        <span className="exam-timer">{fmtTime(remaining)}</span>
      </div>

      {current.media_id && <div className="exam-media muted">[media: {current.media_id}]</div>}

      <p className="exam-prompt"><strong>{current.prompt}</strong></p>

      {current.options.map((o) => {
        const cls = "option" + (currentAnswer?.selected === o.id ? " selected" : "");
        return (
          <button key={o.id} className={cls} onClick={() => choose(current.question_version_id, o.id)}>
            {o.text}
          </button>
        );
      })}

      <div style={{ height: 8 }} />
      <button
        className={"secondary" + (currentAnswer?.marked ? " marked" : "")}
        onClick={() => toggleMark(current.question_version_id)}
      >
        {currentAnswer?.marked ? t("marked") : t("markForReview")}
      </button>

      <div className="navigator">
        {questions.map((q, i) => {
          const a = answers[q.question_version_id];
          let cls = "nav-cell";
          if (i === index) cls += " current";
          else if (a?.marked) cls += " marked";
          else if (a?.selected) cls += " answered";
          return (
            <button key={q.question_version_id} className={cls} onClick={() => setIndex(i)}>
              {q.position}
            </button>
          );
        })}
      </div>

      <div className="exam-actions">
        <button className="secondary" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>
          {t("prev")}
        </button>
        <button
          className="secondary"
          disabled={index >= questions.length - 1}
          onClick={() => setIndex((i) => i + 1)}
        >
          {t("next")}
        </button>
      </div>

      <div style={{ height: 8 }} />
      <button onClick={submit} disabled={busy}>{t("submitExam")}</button>
      {error && <p className="explain">{error}</p>}
    </div>
  );
}

type Screen = "home" | "practice" | "mock";

function Home({ onPick }: { onPick: (s: Screen) => void }) {
  return (
    <div className="card">
      <h1>{t("appTitle")}</h1>
      <p className="muted">{t("tagline")}</p>
      <button onClick={() => onPick("practice")}>{t("practiceMode")}</button>
      <div style={{ height: 8 }} />
      <button onClick={() => onPick("mock")}>{t("startMock")}</button>
    </div>
  );
}

function App() {
  const [user, setUser] = useState<UserOut | null>(null);
  const [onboarded, setOnboarded] = useState(false);
  const [screen, setScreen] = useState<Screen>("home");

  useEffect(() => {
    readyTelegram();
    api.me().then((r) => {
      setUser(r.user);
      setOnboarded(!!r.profile?.onboarding_completed);
    }).catch(() => undefined);
  }, []);

  if (!user) return <Login onLogin={(u) => { setUser(u); setOnboarded(u.onboarding_completed); }} />;
  if (!onboarded) return <Onboarding onDone={() => setOnboarded(true)} />;
  if (screen === "practice") return <Practice onExit={() => setScreen("home")} />;
  if (screen === "mock") return <ExamMode onExit={() => setScreen("home")} />;
  return <Home onPick={setScreen} />;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
