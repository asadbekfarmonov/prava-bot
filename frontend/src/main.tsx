import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import "./ui/tokens.css";
import { api } from "./api";
import { getTelegramInitData, readyTelegram, showBackButton, lockForMock, unlockFromMock } from "./telegram";
import { watchTheme } from "./ui/theme";
import { t, topicLabel } from "./i18n/uz";
import { AdminArea } from "./admin";
import { TheoryArea } from "./theory";
import {
  AppBar, Badge, BottomNav, Button, Card, Chip, EmptyState, Expandable,
  IconAlert, IconCheck, IconExam, IconFlame, IconHome, IconInbox, IconPractice,
  IconProfile, IconTheory, ListRow, OfflineBar, ProgressBar, ProgressRing,
  QuestionMedia, Screen, Skeleton, StatBlock, Tabs, TopicMasteryBar,
  type TabKey
} from "./ui/components";
import type {
  AnswerResult, FullProfileOut, HomeSummary, MistakeItem, MockAttemptState,
  MockReview, NextQuestion, RankingOut, TopicProgressRow, UserOut
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

function optionLabel(position: number): string {
  return "ABCDE"[position - 1] || String(position);
}

// Show the Telegram BackButton while `active`, wired to `onBack`.
function useBackButton(active: boolean, onBack: () => void) {
  useEffect(() => {
    if (!active) return;
    const cleanup = showBackButton(onBack);
    return cleanup;
  }, [active, onBack]);
}

// ------------------------------------------------------------------ Login / onboarding
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
    <Screen full>
      <Card>
        <h1 className="ui-h1">{t("appTitle")}</h1>
        <p className="ui-muted">{t("tagline")}</p>
        {error && <p className="ui-muted">{t("openFromTelegram")}</p>}
        {devAvailable && (
          <Button block onClick={() => api.devLogin().then((r) => onLogin(r.user)).catch((e) => setError(String(e.message)))}>
            {t("devLogin")}
          </Button>
        )}
      </Card>
    </Screen>
  );
}

function Onboarding({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [examDate, setExamDate] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <Screen full>
      <Card>
        <h1 className="ui-h1">{t("onboardingTitle")}</h1>
        <div className="ui-stack" style={{ marginTop: 12 }}>
          <div>
            <label className="ui-field-label">{t("displayName")}</label>
            <input className="ui-input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="ui-field-label">{t("examDate")} ({t("comingSoon") === "" ? "" : ""}—)</label>
            <input className="ui-input" type="date" value={examDate} onChange={(e) => setExamDate(e.target.value)} />
          </div>
          <Button block disabled={busy || name.trim().length === 0}
            onClick={() => {
              setBusy(true);
              api.saveProfile({ display_name: name.trim(), target_exam_date: examDate || null })
                .then(() => onDone()).finally(() => setBusy(false));
            }}>
            {t("save")}
          </Button>
        </div>
      </Card>
    </Screen>
  );
}

// ------------------------------------------------------------------ Practice runner
type RunnerConfig = { source: string; topic: string | null; title: string };

function PracticeRunner({ config, onExit }: { config: RunnerConfig; onExit: () => void }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState<NextQuestion | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [empty, setEmpty] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useBackButton(true, onExit);

  const loadNext = useCallback(async () => {
    setResult(null); setSelected(null); setError(null); setLoading(true);
    try {
      const q = await api.nextQuestion(config.topic, config.source);
      setQuestion(q); setEmpty(false);
    } catch (e) {
      setQuestion(null); setEmpty(true); setError(String((e as Error).message));
    } finally {
      setLoading(false);
    }
  }, [config.source, config.topic]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const s = await api.createSession(config.topic, config.source);
        if (!alive) return;
        setSessionId(s.id);
        await loadNext();
      } catch (e) {
        if (alive) { setError(String((e as Error).message)); setLoading(false); }
      }
    })();
    return () => { alive = false; };
  }, [config.source, config.topic, loadNext]);

  async function submit() {
    if (!sessionId || !question || !selected) return;
    setLoading(true);
    try {
      const r = await api.submitAnswer(sessionId, question.question_id, selected);
      setResult(r);
      setCount((c) => c + 1);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setLoading(false);
    }
  }

  const wrongOptions = useMemo(
    () => (result ? result.options.filter((o) => !o.is_correct && o.explanation) : []),
    [result]
  );
  const correctOpt = result?.options.find((o) => o.is_correct);

  return (
    <Screen>
      <AppBar title={config.title}
        subtitle={question ? `${topicLabel(question.topic)} · ${count + 1}` : undefined} />
      {config.source !== "personalized" && config.source !== "topic" && (
        <Badge>{t("notRealExamNote")}</Badge>
      )}

      {loading && !question && (
        <Card><Skeleton height={180} /><div style={{ height: 12 }} />
          <Skeleton height={44} /><div style={{ height: 8 }} /><Skeleton height={44} /></Card>
      )}

      {empty && !loading && (
        <Card>
          <EmptyState icon={<IconCheck size={40} />}
            title={t("noMistakes")} message={t("emptyMistakesMsg")}
            action={<Button variant="secondary" onClick={onExit}>{t("backHome")}</Button>} />
        </Card>
      )}

      {question && (
        <Card>
          {question.media && <QuestionMedia media={question.media} />}
          <h2 className="ui-h1" style={{ fontSize: 18, marginTop: question.media ? 12 : 0 }}>{question.prompt}</h2>
          <div className="ui-stack ui-stack--sm" style={{ marginTop: 12 }}>
            {question.options.map((o) => {
              let state: "idle" | "selected" | "correct" | "wrong" = "idle";
              if (result) {
                if (o.id === result.correct_option_id) state = "correct";
                else if (o.id === selected) state = "wrong";
              } else if (o.id === selected) state = "selected";
              return (
                <div key={o.id}>
                  <button className={"ui-option" + (state !== "idle" ? ` ui-option--${state}` : "")}
                    disabled={!!result} onClick={() => setSelected(o.id)}>
                    <span className="ui-option__marker">{optionLabel(o.position)}</span>
                    <span>{o.text}</span>
                  </button>
                </div>
              );
            })}
          </div>

          {!result ? (
            <Button block style={{ marginTop: 16 }} disabled={!selected || loading} onClick={submit}>
              {t("submit")}
            </Button>
          ) : (
            <div className="ui-stack" style={{ marginTop: 16 }}>
              <div className="ui-row" style={{ gap: 8 }}>
                {result.is_correct
                  ? <Badge tone="success">✓ {t("correct")}</Badge>
                  : <Badge tone="danger">✕ {t("incorrect")}</Badge>}
                {!result.is_correct && correctOpt && (
                  <span className="ui-text-sm ui-muted">
                    {t("youShort")}: {selected && optionLabel(question.options.find((o) => o.id === selected)?.position ?? 0)} · {t("correctShort")}: {optionLabel(correctOpt.position)}
                  </span>
                )}
              </div>

              {correctOpt && (
                <Expandable defaultOpen tone="success"
                  title={`${t("whyCorrectPrefix")} ${optionLabel(correctOpt.position)}?`}>
                  {correctOpt.explanation || result.short_explanation}
                </Expandable>
              )}
              {wrongOptions.map((o) => (
                <Expandable key={o.id} tone="danger"
                  title={`${t("whyNotPrefix")} ${optionLabel(o.position)} ${t("whyNotSuffix")}`}>
                  {o.explanation}
                </Expandable>
              ))}
              {result.rule && (
                <Expandable title={`${t("ruleSection")} — ${result.rule.code}`}>
                  {result.rule.text}
                </Expandable>
              )}
              <Button block onClick={loadNext}>{t("next")}</Button>
            </div>
          )}
        </Card>
      )}
      {error && !empty && <p className="ui-muted">{error}</p>}
    </Screen>
  );
}

// ------------------------------------------------------------------ Home hub
type Nav = {
  runPractice: (c: RunnerConfig) => void;
  goTab: (tab: TabKey) => void;
  openDetail: (kind: "ranking" | "progress" | "mistakes") => void;
};

function readinessCtaLabel(state: string): string {
  if (state === "insufficient_data") return t("continueCta");
  return t("continueCta");
}

function HomeTab({ nav }: { nav: Nav }) {
  const [home, setHome] = useState<HomeSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    api.home().then(setHome).catch((e) => setError(String(e.message)));
  }, []);
  useEffect(load, [load]);

  const onContinue = useCallback(async () => {
    try {
      const a = await api.nextAction();
      if (a.action === "resume_mock") { nav.goTab("exam"); return; }
      if (a.action === "mistakes") { nav.runPractice({ source: "mistakes", topic: null, title: t("modeMistakes") }); return; }
      if (a.action === "weak_topic" || a.action === "coverage") {
        nav.runPractice({ source: "topic", topic: a.topic, title: topicLabel(a.topic) || t("modeByTopic") });
        return;
      }
      nav.runPractice({ source: "personalized", topic: null, title: t("modeForYou") });
    } catch {
      nav.runPractice({ source: "personalized", topic: null, title: t("modeForYou") });
    }
  }, [nav]);

  if (error) {
    return (
      <Screen>
        <AppBar title={t("appTitle")} />
        <Card><EmptyState icon={<IconAlert size={36} />} message={t("loadFailed")}
          action={<Button onClick={load}>{t("retry")}</Button>} /></Card>
      </Screen>
    );
  }
  if (!home) {
    return (
      <Screen>
        <AppBar title={t("appTitle")} />
        <Skeleton height={22} width="50%" />
        <Card accent><Skeleton height={120} /></Card>
        <Skeleton height={70} /><Skeleton height={70} />
      </Screen>
    );
  }

  const r = home.readiness;
  const cd = home.exam_countdown;
  const dg = home.daily_goal;

  return (
    <Screen>
      <AppBar title={`${t("greeting")}, ${home.display_name}`}
        subtitle={cd
          ? (cd.passed ? t("examPassedDate")
            : cd.days_remaining === 0 ? t("examToday")
            : `${t("readinessTitle")}gacha ${cd.days_remaining} ${t("examCountdownSuffix")}`)
          : undefined} />

      {/* Readiness card — the single accent surface */}
      <Card accent>
        <div className="ui-row ui-row--between">
          <div className="ui-stack ui-stack--sm">
            <span className="ui-stat__label" style={{ color: "rgba(255,255,255,0.85)" }}>
              {r.state === "initial" ? t("initialLevel") : t("readinessTitle")}
            </span>
            <span style={{ fontSize: 15, fontWeight: 600 }}>{r.label}</span>
            {r.exam_ready && <Badge tone="success">{t("examReadyBadge")} ✓</Badge>}
          </div>
          <ProgressRing percent={r.score} size={92} label={r.label} />
        </div>
        {home.last_mock ? (
          <div className="ui-statrow" style={{ marginTop: 12 }}>
            <StatBlock value={`${home.last_mock.correct_count}/${home.last_mock.question_count}`} label={t("lastMockLabel")} />
            <StatBlock value={r.unique_questions_attempted} label={t("seenLabel")} />
            <StatBlock value={home.recommendations.mistakes_open} label={t("mistakes")} />
            <StatBlock value={`🔥 ${home.streak.current}`} label={t("streakLabel")} />
          </div>
        ) : (
          <div className="ui-statrow" style={{ marginTop: 12 }}>
            <StatBlock value={r.unique_questions_attempted} label={t("seenLabel")} />
            <StatBlock value={home.recommendations.mistakes_open} label={t("mistakes")} />
            <StatBlock value={`🔥 ${home.streak.current}`} label={t("streakLabel")} />
          </div>
        )}
        <Button variant="onaccent" block style={{ marginTop: 16 }} onClick={onContinue}>
          {readinessCtaLabel(r.state)}
        </Button>
      </Card>

      {/* Daily goal */}
      {dg.goal != null && (
        <Card flat>
          <div className="ui-row ui-row--between" style={{ marginBottom: 8 }}>
            <span style={{ fontWeight: 600 }}>{t("dailyGoalTitle")}</span>
            <span className="ui-muted">{dg.answered_today}/{dg.goal}</span>
          </div>
          <ProgressBar value={dg.answered_today} max={dg.goal} />
        </Card>
      )}

      {/* Recommendations */}
      <div>
        <p className="ui-field-label">{t("forYou")}</p>
        <div className="ui-stack ui-stack--sm">
          {home.recommendations.weak_topic && (
            <ListRow icon={<IconPractice size={20} />}
              title={home.recommendations.weak_topic.label}
              subtitle={`${Math.round(home.recommendations.weak_topic.mastery * 100)}% · ${t("practiceWord")}`}
              onClick={() => nav.runPractice({ source: "topic", topic: home.recommendations.weak_topic!.topic, title: home.recommendations.weak_topic!.label })} />
          )}
          {home.recommendations.mistakes_open > 0 && (
            <ListRow icon={<IconInbox size={20} />}
              title={t("modeMistakes")}
              subtitle={`${home.recommendations.mistakes_open} · ${t("repeatWord")}`}
              onClick={() => nav.openDetail("mistakes")} />
          )}
          {!home.recommendations.weak_topic && home.recommendations.mistakes_open === 0 && (
            <ListRow icon={<IconFlame size={20} />} title={t("modeForYou")} subtitle={t("modeForYouSub")}
              onClick={() => nav.runPractice({ source: "personalized", topic: null, title: t("modeForYou") })} />
          )}
        </div>
      </div>

      {/* Quick access */}
      <div>
        <p className="ui-field-label">{t("quickAccess")}</p>
        <div className="ui-grid-2">
          <Button variant="secondary" onClick={() => nav.goTab("theory")}>{t("theory")}</Button>
          <Button variant="secondary" onClick={() => nav.goTab("theory")}>{t("signs")}</Button>
          <Button variant="secondary" onClick={() => nav.goTab("exam")}>{t("modeRealExam")}</Button>
          <Button variant="secondary" onClick={() => nav.openDetail("ranking")}>{t("ranking")}</Button>
        </div>
        <div style={{ height: 8 }} />
        <Button variant="ghost" block onClick={() => nav.openDetail("progress")}>{t("progress")}</Button>
      </div>
    </Screen>
  );
}

// ------------------------------------------------------------------ Progress detail
function ProgressDetail({ onExit }: { onExit: () => void }) {
  const [rows, setRows] = useState<TopicProgressRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useBackButton(true, onExit);
  const load = useCallback(() => {
    setError(null);
    api.topicProgress().then((r) => setRows(r.topics)).catch((e) => setError(String(e.message)));
  }, []);
  useEffect(load, [load]);

  return (
    <Screen>
      <AppBar title={t("progressTitle")} />
      {error && <Card><EmptyState message={t("loadFailed")} action={<Button onClick={load}>{t("retry")}</Button>} /></Card>}
      {!rows && !error && <Card><Skeleton height={40} /><div style={{ height: 8 }} /><Skeleton height={40} /></Card>}
      {rows && (
        <Card>
          <div className="ui-stack">
            {rows.map((row) => (
              <TopicMasteryBar key={row.topic} label={row.label} mastery={row.mastery}
                hint={row.needs_more_practice ? t("needsMorePractice") : `${row.answered} ${t("answered")}`} />
            ))}
          </div>
        </Card>
      )}
    </Screen>
  );
}

// ------------------------------------------------------------------ Ranking detail
function RankingDetail({ onExit }: { onExit: () => void }) {
  const [range, setRange] = useState<"week" | "month" | "all">("week");
  const [data, setData] = useState<RankingOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  useBackButton(true, onExit);
  useEffect(() => {
    setData(null); setError(null);
    api.ranking(range).then(setData).catch((e) => setError(String(e.message)));
  }, [range]);

  const ownInList = data ? data.entries.some((e) => e.is_self) : false;
  return (
    <Screen>
      <AppBar title={t("ranking")} />
      <Tabs value={range} onChange={setRange}
        options={[["week", t("rankingWeek")], ["month", t("rankingMonth")], ["all", t("rankingAll")]]} />
      {error && <Card><EmptyState message={t("loadFailed")} /></Card>}
      {!data && !error && <Card><Skeleton height={40} /><Skeleton height={40} /></Card>}
      {data && data.entries.length === 0 && (
        <Card><EmptyState icon={<IconInbox size={36} />} message={t("rankingNeedMsg")} /></Card>
      )}
      {data && data.entries.length > 0 && (
        <Card flat>
          <div className="ui-stack ui-stack--sm">
            {data.entries.map((row) => (
              <div key={row.position} className="ui-row ui-row--between"
                style={{ padding: "8px 6px", borderRadius: 10, background: row.is_self ? "var(--accent-soft)" : "transparent" }}>
                <span>{row.position}. {row.is_self ? `${row.name} (${t("you")})` : row.name}</span>
                <strong>{row.points}</strong>
              </div>
            ))}
            {!ownInList && (
              <div className="ui-row ui-row--between" style={{ padding: "8px 6px", borderRadius: 10, background: "var(--accent-soft)" }}>
                <span>{data.own.position}. {data.own.name} ({t("you")})</span>
                <strong>{data.own.points}</strong>
              </div>
            )}
          </div>
        </Card>
      )}
    </Screen>
  );
}

// ------------------------------------------------------------------ Mistakes detail
function MistakesDetail({ onExit, onPractice }: { onExit: () => void; onPractice: () => void }) {
  const [items, setItems] = useState<MistakeItem[] | null>(null);
  const [filter, setFilter] = useState<"recent" | "most" | "all">("all");
  const [error, setError] = useState<string | null>(null);
  useBackButton(true, onExit);
  useEffect(() => {
    api.mistakes().then((r) => setItems(r.mistakes)).catch((e) => setError(String(e.message)));
  }, []);

  const sorted = useMemo(() => {
    if (!items) return [];
    const arr = [...items];
    if (filter === "most") arr.sort((a, b) => b.miss_count - a.miss_count);
    else if (filter === "recent") arr.sort((a, b) => (b.last_missed_at || "").localeCompare(a.last_missed_at || ""));
    return arr;
  }, [items, filter]);

  const byTopic = useMemo(() => {
    const m: Record<string, number> = {};
    (items || []).forEach((i) => { const k = i.topic || "?"; m[k] = (m[k] || 0) + 1; });
    return m;
  }, [items]);

  return (
    <Screen>
      <AppBar title={t("mistakesTitle")} subtitle={items ? `${items.length}` : undefined} />
      {error && <Card><EmptyState message={t("loadFailed")} /></Card>}
      {!items && !error && <Card><Skeleton height={40} /><Skeleton height={40} /></Card>}
      {items && items.length === 0 && (
        <Card><EmptyState icon={<IconCheck size={40} />} title={t("noMistakes")} message={t("emptyMistakesMsg")} /></Card>
      )}
      {items && items.length > 0 && (
        <>
          <div className="ui-chips">
            {Object.entries(byTopic).map(([k, v]) => (
              <Badge key={k}>{topicLabel(k)} {v}</Badge>
            ))}
          </div>
          <Tabs value={filter} onChange={setFilter}
            options={[["recent", "Oxirgi"], ["most", "Ko'p"], ["all", "Barcha"]]} />
          <Card flat>
            <div className="ui-stack ui-stack--sm">
              {sorted.map((m) => (
                <div key={m.question_id} className="ui-row ui-row--between" style={{ padding: "6px 0" }}>
                  <span className="ui-text-sm">{m.prompt || topicLabel(m.topic)}</span>
                  <Badge tone="danger">{m.miss_count}</Badge>
                </div>
              ))}
            </div>
          </Card>
          <Button block onClick={onPractice}>{t("startMistakes")}</Button>
        </>
      )}
    </Screen>
  );
}

// ------------------------------------------------------------------ Practice hub tab
function PracticeTab({ nav }: { nav: Nav }) {
  const [picking, setPicking] = useState(false);
  return (
    <Screen>
      <AppBar title={t("practiceHub")} />
      <div className="ui-stack ui-stack--sm">
        <ListRow icon={<IconFlame size={20} />} title={t("modeForYou")} subtitle={t("modeForYouSub")}
          onClick={() => nav.runPractice({ source: "personalized", topic: null, title: t("modeForYou") })} />
        <ListRow icon={<IconPractice size={20} />} title={t("modeByTopic")} subtitle={t("modeByTopicSub")}
          onClick={() => setPicking((v) => !v)} />
        {picking && (
          <Card flat>
            <div className="ui-chips">
              {TOPICS.map((tp) => (
                <Chip key={tp} onClick={() => nav.runPractice({ source: "topic", topic: tp, title: topicLabel(tp) })}>
                  {topicLabel(tp)}
                </Chip>
              ))}
            </div>
          </Card>
        )}
        <ListRow icon={<IconInbox size={20} />} title={t("modeMistakes")} subtitle={t("modeMistakesSub")}
          onClick={() => nav.openDetail("mistakes")} />
        <ListRow icon={<IconTheory size={20} />} title={t("modeSigns")} subtitle={t("modeSignsSub")}
          onClick={() => nav.runPractice({ source: "sign_trainer", topic: null, title: t("modeSigns") })} />
        <ListRow icon={<IconExam size={20} />} title={t("modeRealExam")} subtitle={t("modeRealExamSub")}
          onClick={() => nav.goTab("exam")} />
      </div>
      <div>
        <p className="ui-field-label">{t("comingSoon")}</p>
        <div className="ui-chips">
          <Chip disabled>{t("mode50")}</Chip>
          <Chip disabled>{t("mode100")}</Chip>
          <Chip disabled>{t("modeTickets")}</Chip>
        </div>
      </div>
    </Screen>
  );
}

// ------------------------------------------------------------------ Exam (isolated mock)
type LocalAnswer = { selected: string | null; marked: boolean };

function ExamResult({ attempt, onReview, onAgain, onHome }: {
  attempt: MockAttemptState; onReview: () => void; onAgain: () => void; onHome: () => void;
}) {
  const r = attempt.result;
  return (
    <Screen full>
      <div className="card exam">
        <h1 style={{ fontSize: 26 }}>
          {attempt.correct_count} / {attempt.question_count}{" "}
          <span className={attempt.passed ? "pass" : "fail"}>{attempt.passed ? t("passed") : t("failed")}</span>
        </h1>
        {r && r.avg_answer_time_seconds != null && (
          <p className="muted">{t("avgAnswerTime")}: {Math.round(r.avg_answer_time_seconds)} s</p>
        )}
        {r && r.missed.length > 0 && (
          <>
            <p><strong>{t("missedQuestions")}:</strong></p>
            <ul>{r.missed.map((m) => (
              <li key={m.question_version_id} className="explain">{m.position} · {topicLabel(m.topic)}</li>
            ))}</ul>
          </>
        )}
        <div style={{ height: 12 }} />
        <button className="option" onClick={onReview}>{t("reviewAnswers")}</button>
        <div style={{ height: 8 }} />
        <div className="exam-actions">
          <button onClick={onAgain}>{t("againExam")}</button>
          <button className="secondary" onClick={onHome}>{t("backHome")}</button>
        </div>
      </div>
    </Screen>
  );
}

function ExamReview({ review, onExit }: { review: MockReview; onExit: () => void }) {
  useBackButton(true, onExit);
  return (
    <Screen full>
      <div className="card exam">
        <h1>{t("reviewAnswers")}</h1>
        {review.items.map((item) => (
          <div key={item.question_version_id} className="review-item">
            <p className="muted">{item.position} / {review.question_count}</p>
            {item.media && <QuestionMedia media={item.media} />}
            <p><strong>{item.prompt}</strong></p>
            {item.options.map((o) => {
              let cls = "option";
              if (o.id === item.correct_option_id) cls += " correct";
              else if (o.id === item.selected_option_id) cls += " wrong";
              return <div key={o.id}><div className={cls}>{optionLabel(o.position)}. {o.text}</div>
                <div className="explain">{o.explanation}</div></div>;
            })}
            {item.rule && <div className="rule"><strong>{t("rule")}: {item.rule.code}</strong>
              <p className="explain">{item.rule.text}</p></div>}
          </div>
        ))}
        <button className="secondary" onClick={onExit}>{t("backHome")}</button>
      </div>
    </Screen>
  );
}

function ExamTab({ onMockActive }: { onMockActive: (active: boolean) => void }) {
  const [attempt, setAttempt] = useState<MockAttemptState | null>(null);
  const [review, setReview] = useState<MockReview | null>(null);
  const [answers, setAnswers] = useState<Record<string, LocalAnswer>>({});
  const [index, setIndex] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const [phase, setPhase] = useState<"entry" | "active" | "result">("entry");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAttempt = useCallback((a: MockAttemptState) => {
    setAttempt(a);
    setRemaining(a.remaining_seconds);
    const map: Record<string, LocalAnswer> = {};
    for (const q of a.questions) map[q.question_version_id] = { selected: q.selected_option_id, marked: q.marked_for_review };
    setAnswers(map);
  }, []);

  // On mount, resume an in-progress mock (supports the Home resume path).
  useEffect(() => {
    api.currentMock().then((a) => {
      if (a.status === "in_progress") { loadAttempt(a); setPhase("active"); }
    }).catch(() => undefined);
  }, [loadAttempt]);

  const active = phase === "active" && attempt?.status === "in_progress";
  useEffect(() => {
    onMockActive(!!active);
    if (active) lockForMock(); else unlockFromMock();
    return () => { unlockFromMock(); };
  }, [active, onMockActive]);

  async function begin() {
    setBusy(true); setError(null);
    try {
      let a: MockAttemptState | null = null;
      try { a = await api.currentMock(); } catch { a = null; }
      if (!a || a.status !== "in_progress") a = await api.startMock();
      loadAttempt(a); setIndex(0); setPhase("active");
    } catch (e) { setError(String((e as Error).message)); }
    finally { setBusy(false); }
  }

  const submit = useCallback(async () => {
    if (!attempt) return;
    setBusy(true);
    try { const done = await api.submitMock(attempt.id); setAttempt(done); setPhase("result"); }
    catch (e) { setError(String((e as Error).message)); }
    finally { setBusy(false); }
  }, [attempt]);

  useEffect(() => {
    if (!active) return;
    if (remaining <= 0) { void submit(); return; }
    const id = window.setTimeout(() => setRemaining((x) => x - 1), 1000);
    return () => window.clearTimeout(id);
  }, [active, remaining, submit]);

  async function choose(qvid: string, optionId: string) {
    const prev = answers[qvid] || { selected: null, marked: false };
    const next = { selected: optionId, marked: prev.marked };
    setAnswers((m) => ({ ...m, [qvid]: next }));
    try { await api.saveMockAnswer(attempt!.id, qvid, optionId, next.marked); }
    catch (e) { setError(String((e as Error).message)); }
  }

  if (review) return <ExamReview review={review} onExit={() => { setReview(null); setPhase("entry"); setAttempt(null); }} />;

  if (phase === "result" && attempt) {
    return <ExamResult attempt={attempt}
      onReview={() => api.reviewMock(attempt.id).then(setReview).catch((e) => setError(String(e.message)))}
      onAgain={() => { setAttempt(null); setPhase("entry"); }}
      onHome={() => { setAttempt(null); setPhase("entry"); }} />;
  }

  if (!active) {
    return (
      <Screen>
        <AppBar title={t("examEntryTitle")} />
        <Card>
          <h2 className="ui-h1" style={{ fontSize: 18 }}>{t("examEntrySummary")}</h2>
          <p className="ui-muted" style={{ marginTop: 8 }}>{t("examEntryWarn")}</p>
          {error && <p className="ui-muted">{error}</p>}
          <Button block style={{ marginTop: 16 }} disabled={busy} onClick={begin}>{t("examStartBtn")}</Button>
        </Card>
      </Screen>
    );
  }

  const questions = attempt!.questions;
  const current = questions[index];
  const currentAnswer = answers[current.question_version_id];
  const danger = remaining < 120;

  return (
    <div className="ui-screen ui-screen--full">
      <div className="card exam">
        <div className="exam-bar">
          <span>{current.position} / {attempt!.question_count}</span>
          <span className="exam-timer" style={danger ? { color: "#ff6b6b" } : undefined}>{fmtTime(remaining)}</span>
        </div>
        {current.media && <QuestionMedia media={current.media} />}
        <p className="exam-prompt"><strong>{current.prompt}</strong></p>
        {current.options.map((o) => {
          const cls = "option" + (currentAnswer?.selected === o.id ? " selected" : "");
          return <button key={o.id} className={cls} onClick={() => choose(current.question_version_id, o.id)}>
            {optionLabel(o.position)}. {o.text}</button>;
        })}
        <div className="navigator">
          {questions.map((q, i) => {
            const a = answers[q.question_version_id];
            let cls = "nav-cell";
            if (i === index) cls += " current";
            else if (a?.marked) cls += " marked";
            else if (a?.selected) cls += " answered";
            return <button key={q.question_version_id} className={cls} onClick={() => setIndex(i)}>{q.position}</button>;
          })}
        </div>
        <div className="exam-actions">
          <button className="secondary" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>{t("prev")}</button>
          <button className="secondary" disabled={index >= questions.length - 1} onClick={() => setIndex((i) => i + 1)}>{t("next")}</button>
        </div>
        <div style={{ height: 8 }} />
        <button onClick={submit} disabled={busy}>{t("submitExam")}</button>
        {error && <p className="explain">{error}</p>}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ Profile tab
function ProfileTab({ user, onLogout, onOpenAdmin }: {
  user: UserOut; onLogout: () => void; onOpenAdmin: () => void;
}) {
  const [profile, setProfile] = useState<FullProfileOut | null>(null);
  const [home, setHome] = useState<HomeSummary | null>(null);
  const [examDate, setExamDate] = useState("");
  const [rankingName, setRankingName] = useState("");
  const [showRanking, setShowRanking] = useState(true);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.me().then((r) => {
      setProfile(r.profile);
      if (r.profile) {
        setExamDate(r.profile.target_exam_date || "");
        setRankingName(r.profile.ranking_name || "");
        setShowRanking(r.profile.show_on_ranking);
      }
    }).catch(() => undefined);
    api.home().then(setHome).catch(() => undefined);
  }, []);

  async function save() {
    if (!profile?.display_name) return;
    setBusy(true); setSaved(false);
    try {
      await api.saveProfile({
        display_name: profile.display_name,
        target_exam_date: examDate || null,
        ranking_name: rankingName || null,
        show_on_ranking: showRanking
      });
      setSaved(true);
    } finally { setBusy(false); }
  }

  return (
    <Screen>
      <AppBar title={t("tabProfile")} subtitle={profile?.display_name || user.first_name || undefined} />
      {home && (
        <Card>
          <div className="ui-statrow">
            <StatBlock value={`🔥 ${home.streak.current}`} label={t("streakLabel")} />
            <StatBlock value={home.readiness.unique_questions_attempted} label={t("questionsAnswered")} />
            <StatBlock value={home.ranking.all.position ?? "—"} label={t("rankingPosition")} />
          </div>
          {home.last_mock && (
            <p className="ui-muted" style={{ marginTop: 10 }}>
              {t("mockHistory")}: {home.last_mock.correct_count}/{home.last_mock.question_count}
            </p>
          )}
        </Card>
      )}

      <Card>
        <div className="ui-stack">
          <div>
            <label className="ui-field-label">{t("examDate")}</label>
            <input className="ui-input" type="date" value={examDate} onChange={(e) => setExamDate(e.target.value)} />
          </div>
          <div>
            <label className="ui-field-label">{t("rankingName")}</label>
            <input className="ui-input" value={rankingName} onChange={(e) => setRankingName(e.target.value)} />
          </div>
          <label className="ui-row" style={{ gap: 8 }}>
            <input type="checkbox" checked={showRanking} onChange={(e) => setShowRanking(e.target.checked)} />
            <span>{t("showOnRanking")}</span>
          </label>
          <div className="ui-row" style={{ gap: 8 }}>
            <Button disabled={busy} onClick={save}>{t("saveChanges")}</Button>
            {saved && <Badge tone="success">{t("saved2")}</Badge>}
          </div>
        </div>
      </Card>

      <Card flat>
        <div className="ui-row ui-row--between"><span className="ui-muted">{t("categoryLabel")}</span><span>{profile?.category || "B"}</span></div>
        <div className="ui-row ui-row--between"><span className="ui-muted">{t("languageLabel")}</span><span>{profile?.language || "uz"}</span></div>
      </Card>

      {user.admin_role && (
        <Button variant="secondary" block onClick={onOpenAdmin}>{t("adminStudio")}</Button>
      )}
      <Button variant="ghost" block onClick={onLogout}>{t("logout")}</Button>
    </Screen>
  );
}

// ------------------------------------------------------------------ App shell
type Detail =
  | { kind: "practice"; config: RunnerConfig }
  | { kind: "ranking" }
  | { kind: "progress" }
  | { kind: "mistakes" }
  | null;

function App() {
  const [user, setUser] = useState<UserOut | null>(null);
  const [onboarded, setOnboarded] = useState(false);
  const [tab, setTab] = useState<TabKey>("home");
  const [detail, setDetail] = useState<Detail>(null);
  const [adminOpen, setAdminOpen] = useState(false);
  const [mockActive, setMockActive] = useState(false);
  const [offline, setOffline] = useState(!navigator.onLine);

  useEffect(() => {
    readyTelegram();
    watchTheme();
    api.me().then((r) => { setUser(r.user); setOnboarded(!!r.profile?.onboarding_completed); }).catch(() => undefined);
    const on = () => setOffline(false);
    const off = () => setOffline(true);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);

  const nav: Nav = useMemo(() => ({
    runPractice: (config) => setDetail({ kind: "practice", config }),
    goTab: (target) => { setDetail(null); setAdminOpen(false); setTab(target); },
    openDetail: (kind) => setDetail({ kind })
  }), []);

  if (!user) return <div className="ui-app"><Login onLogin={(u) => { setUser(u); setOnboarded(u.onboarding_completed); }} /></div>;
  if (!onboarded) return <div className="ui-app"><Onboarding onDone={() => setOnboarded(true)} /></div>;
  if (adminOpen) return <div className="ui-app"><Screen><AdminArea role={user.admin_role} onExit={() => setAdminOpen(false)} /></Screen></div>;

  const navItems = [
    { key: "home" as TabKey, label: t("tabHome"), icon: IconHome },
    { key: "practice" as TabKey, label: t("tabPractice"), icon: IconPractice },
    { key: "theory" as TabKey, label: t("tabTheory"), icon: IconTheory },
    { key: "exam" as TabKey, label: t("tabExam"), icon: IconExam },
    { key: "profile" as TabKey, label: t("tabProfile"), icon: IconProfile }
  ];

  let content: React.ReactNode;
  if (detail?.kind === "practice") {
    content = <PracticeRunner config={detail.config} onExit={() => setDetail(null)} />;
  } else if (detail?.kind === "ranking") {
    content = <RankingDetail onExit={() => setDetail(null)} />;
  } else if (detail?.kind === "progress") {
    content = <ProgressDetail onExit={() => setDetail(null)} />;
  } else if (detail?.kind === "mistakes") {
    content = <MistakesDetail onExit={() => setDetail(null)}
      onPractice={() => setDetail({ kind: "practice", config: { source: "mistakes", topic: null, title: t("modeMistakes") } })} />;
  } else if (tab === "home") {
    content = <HomeTab nav={nav} />;
  } else if (tab === "practice") {
    content = <PracticeTab nav={nav} />;
  } else if (tab === "theory") {
    content = <TheoryArea onExit={() => nav.goTab("home")} />;
  } else if (tab === "exam") {
    content = <ExamTab onMockActive={setMockActive} />;
  } else {
    content = <ProfileTab user={user}
      onLogout={() => api.logout().then(() => { setUser(null); setOnboarded(false); }).catch(() => undefined)}
      onOpenAdmin={() => setAdminOpen(true)} />;
  }

  const hideNav = mockActive;
  return (
    <div className="ui-app">
      {offline && <div style={{ padding: "8px 16px" }}><OfflineBar message={t("offlineMsg")} /></div>}
      {content}
      {!hideNav && (
        <BottomNav active={tab} items={navItems}
          onChange={(k) => { setDetail(null); setAdminOpen(false); setTab(k); }} />
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
