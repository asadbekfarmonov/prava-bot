import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { api, theoryApi } from "./api";
import { t } from "./i18n/uz";
import type { Dict } from "./i18n/uz";
import {
  AppBar, Badge, BottomSheet, Button, Card, Chip, EmptyState, Expandable,
  IconAlert, IconCheck, ListRow, QuestionMedia, Screen, Skeleton
} from "./ui/components";
import type {
  AnswerResult,
  FavoriteItem,
  GestureCard,
  GestureDetail,
  LightCard,
  LightDetail,
  MarkingCard,
  MarkingDetail,
  SearchResult,
  SignCard,
  SignDetail,
  TheoryArticle,
  TheoryArticleCard,
  TheoryBlock,
  TheoryRule,
  TheorySection,
  TheorySectionCard,
  TheoryPracticeStart
} from "./types";

// --------------------------------------------------------------------------- constants
const FAMILIES: Array<[string, keyof Dict]> = [
  ["", "allFamilies"],
  ["warning", "familyWarning"],
  ["priority", "familyPriority"],
  ["prohibitory", "familyProhibitory"],
  ["mandatory", "familyMandatory"],
  ["information", "familyInformation"],
  ["service", "familyService"],
  ["additional_plate", "familyAdditionalPlate"]
];

type ReportTarget = "section" | "article" | "sign" | "marking" | "gesture" | "light" | "rule";
type ReportReason = "wrong_answer" | "unclear_explanation" | "image_problem" | "outdated_rule" | "typo" | "other";
const REPORT_REASONS: Array<[ReportReason, keyof Dict]> = [
  ["wrong_answer", "reasonWrongAnswer"],
  ["unclear_explanation", "reasonUnclear"],
  ["image_problem", "reasonImage"],
  ["outdated_rule", "reasonOutdated"],
  ["typo", "reasonTypo"],
  ["other", "reasonOther"]
];

function optionLabel(position: number): string {
  return "ABCDE"[position - 1] || String(position);
}

function resultTypeLabel(type: SearchResult["type"]): string {
  switch (type) {
    case "section": return t("sections");
    case "article": return t("articleKind");
    case "sign": return t("signs");
    case "marking": return t("markings");
    case "gesture": return t("gestures");
    case "light": return t("lights");
    case "rule": return t("rule");
  }
}

// --------------------------------------------------------------------------- data fetching
// Generic fetch hook with explicit loading / error / retry. Every screen uses it so no
// fetch swallows errors: failures surface as an error state with a retry button.
function useFetch<T>(fn: () => Promise<T>, deps: React.DependencyList) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const reload = useCallback(() => setNonce((n) => n + 1), []);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    fn()
      .then((d) => { if (alive) { setData(d); setLoading(false); } })
      .catch((e: unknown) => { if (alive) { setError(String((e as Error).message)); setLoading(false); } });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);
  return { data, loading, error, reload };
}

// Shared loading (skeleton) / error (retry) surface, rendered while data is not ready.
function LoadOrError({ error, onRetry, rows = 3 }: { error: string | null; onRetry: () => void; rows?: number }) {
  if (error) {
    return (
      <Card>
        <EmptyState icon={<IconAlert size={36} />} message={t("loadFailed")}
          action={<Button onClick={onRetry}>{t("retry")}</Button>} />
      </Card>
    );
  }
  return (
    <Card>
      {Array.from({ length: rows }).map((_, i) => (
        <Fragment key={i}>
          <Skeleton height={44} />
          {i < rows - 1 && <div style={{ height: 8 }} />}
        </Fragment>
      ))}
    </Card>
  );
}

// --------------------------------------------------------------------------- safe block renderer
// SAFE block renderer: fixed component set, TEXT NODES ONLY (no raw HTML injection).
function Block({ block }: { block: TheoryBlock }) {
  const body = block.body || "";
  switch (block.type) {
    case "rule_callout":
      return (
        <div className="rule theory-rule">
          {block.rule && <strong>{t("rule")}: {block.rule.code}</strong>}
          {block.rule?.text && <p className="explain">{block.rule.text}</p>}
          {body && <p className="explain">{body}</p>}
        </div>
      );
    case "warning":
      return <div className="theory-callout warn"><p>{body}</p></div>;
    case "memory_tip":
      return <div className="theory-callout tip"><strong>{t("memoryTip")}</strong><p>{body}</p></div>;
    case "example":
      return <div className="theory-callout example"><p>{body}</p></div>;
    case "image":
    case "diagram":
    case "animation":
      return (
        <figure className="theory-figure">
          <QuestionMedia media={block.media} url={block.media_url}
            mediaType={block.type === "animation" ? "video" : "image"} alt={body || block.type} />
          {body && <figcaption className="muted">{body}</figcaption>}
        </figure>
      );
    case "comparison": {
      const pairs = (block.data?.pairs as Array<{ left: string; right: string }>) || [];
      return (
        <div className="theory-compare">
          {pairs.map((p, i) => (
            <div key={i} className="theory-compare-row">
              <span>{p.left}</span><span>{p.right}</span>
            </div>
          ))}
          {body && <p className="explain">{body}</p>}
        </div>
      );
    }
    case "table": {
      const headers = (block.data?.headers as string[]) || [];
      const rows = (block.data?.rows as string[][]) || [];
      return (
        <table className="theory-table">
          {headers.length > 0 && (
            <thead><tr>{headers.map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
          )}
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri}>{row.map((cell, ci) => <td key={ci}>{cell}</td>)}</tr>
            ))}
          </tbody>
        </table>
      );
    }
    case "practice_link":
      return <div className="theory-callout example"><p>{body || t("linkedQuestions")}</p></div>;
    case "text":
    default:
      return <p className="theory-text">{body}</p>;
  }
}

function RuleCard({ rule }: { rule: TheoryRule }) {
  return (
    <div className="rule theory-rule">
      <strong>{t("rule")}: {rule.code}</strong>
      {rule.text && <p className="explain">{rule.text}</p>}
    </div>
  );
}

// --------------------------------------------------------------------------- favourites toggle
function FavButton({ targetType, targetId }: { targetType: string; targetId: string }) {
  const [saved, setSaved] = useState(false);
  const [favId, setFavId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      if (saved && favId) {
        await theoryApi.removeFavorite(favId);
        setSaved(false);
        setFavId(null);
      } else {
        const r = await theoryApi.addFavorite(targetType, targetId);
        setSaved(true);
        setFavId(r.id);
      }
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="ui-stack ui-stack--sm">
      <Button variant="secondary" disabled={busy} onClick={toggle}>
        {saved ? `★ ${t("saved")}` : `☆ ${t("save2")}`}
      </Button>
      {error && <p className="ui-muted">{error}</p>}
    </div>
  );
}

// --------------------------------------------------------------------------- content report
function ReportSheet({ targetType, targetId, onClose }:
  { targetType: ReportTarget; targetId: string; onClose: () => void }) {
  const [reason, setReason] = useState<ReportReason | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!reason) return;
    setBusy(true);
    setError(null);
    try {
      await theoryApi.report(targetType, targetId, reason, note.trim() || undefined);
      setDone(true);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <BottomSheet onClose={onClose}>
      <h2 className="ui-h1" style={{ fontSize: 18 }}>{t("reportIssue")}</h2>
      {done ? (
        <div className="ui-stack" style={{ marginTop: 12 }}>
          <Badge tone="success"><IconCheck size={16} /> {t("reportSent")}</Badge>
          <Button block onClick={onClose}>{t("back")}</Button>
        </div>
      ) : (
        <div className="ui-stack" style={{ marginTop: 12 }}>
          <p className="ui-field-label">{t("reportReason")}</p>
          <div className="ui-chips">
            {REPORT_REASONS.map(([key, labelKey]) => (
              <Chip key={key} active={reason === key} onClick={() => setReason(key)}>{t(labelKey)}</Chip>
            ))}
          </div>
          <textarea className="ui-input" style={{ minHeight: 84, padding: 8, resize: "vertical" }}
            placeholder={t("reportNotePlaceholder")} value={note}
            onChange={(e) => setNote(e.target.value)} />
          {error && <p className="ui-muted">{error}</p>}
          <div className="ui-row" style={{ gap: 8 }}>
            <Button block disabled={!reason || busy} onClick={submit}>{t("reportSend")}</Button>
            <Button variant="secondary" onClick={onClose}>{t("cancel")}</Button>
          </div>
        </div>
      )}
    </BottomSheet>
  );
}

function ReportButton({ targetType, targetId }: { targetType: ReportTarget; targetId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="ghost" onClick={() => setOpen(true)}>{t("reportIssue")}</Button>
      {open && <ReportSheet targetType={targetType} targetId={targetId} onClose={() => setOpen(false)} />}
    </>
  );
}

// --------------------------------------------------------------------------- in-theory practice
// No-answer-leak runner: correctness / explanations only appear AFTER submit (from `result`).
function TheoryPractice({ start, onExit }: { start: TheoryPracticeStart; onExit: () => void }) {
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const q = start.questions[index];

  const submit = async () => {
    if (!q || !selected) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.submitAnswer(start.session_id, q.question_id, selected);
      setResult(r);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };
  const next = () => {
    setResult(null);
    setSelected(null);
    setIndex((i) => i + 1);
  };

  if (!q) {
    return (
      <Screen>
        <AppBar title={t("practiceThis")} />
        <Card>
          <EmptyState icon={<IconCheck size={40} />} message={t("noResults")}
            action={<Button onClick={onExit}>{t("back")}</Button>} />
        </Card>
      </Screen>
    );
  }
  return (
    <Screen>
      <AppBar title={t("practiceThis")} subtitle={`${index + 1} / ${start.questions_total}`}
        right={<Button variant="ghost" onClick={onExit}>{t("back")}</Button>} />
      <Card>
        {q.media && <QuestionMedia media={q.media} />}
        <h2 className="ui-h1" style={{ fontSize: 18, marginTop: q.media ? 12 : 0 }}>{q.prompt}</h2>
        <div className="ui-stack ui-stack--sm" style={{ marginTop: 12 }}>
          {q.options.map((o) => {
            let state: "idle" | "selected" | "correct" | "wrong" = "idle";
            if (result) {
              if (o.id === result.correct_option_id) state = "correct";
              else if (o.id === selected) state = "wrong";
            } else if (o.id === selected) {
              state = "selected";
            }
            const graded = result?.options.find((g) => g.id === o.id);
            return (
              <div key={o.id}>
                <button className={"ui-option" + (state !== "idle" ? ` ui-option--${state}` : "")}
                  disabled={!!result} onClick={() => setSelected(o.id)}>
                  <span className="ui-option__marker">{optionLabel(o.position)}</span>
                  <span>{o.text}</span>
                </button>
                {graded && graded.explanation && <div className="explain">{graded.explanation}</div>}
              </div>
            );
          })}
        </div>
        {!result ? (
          <Button block style={{ marginTop: 16 }} disabled={!selected || busy} onClick={submit}>{t("submit")}</Button>
        ) : (
          <div className="ui-stack" style={{ marginTop: 16 }}>
            {result.is_correct
              ? <Badge tone="success">✓ {t("correct")}</Badge>
              : <Badge tone="danger">✕ {t("incorrect")}</Badge>}
            {result.rule && (
              <Expandable defaultOpen title={`${t("rule")} — ${result.rule.code}`}>{result.rule.text}</Expandable>
            )}
            <Button block onClick={next}>{t("next")}</Button>
          </div>
        )}
        {error && <p className="ui-muted">{error}</p>}
      </Card>
    </Screen>
  );
}

// --------------------------------------------------------------------------- theory area
export type TheoryView =
  | { name: "home" }
  | { name: "section"; slug: string }
  | { name: "article"; slug: string }
  | { name: "signs" }
  | { name: "sign"; code: string }
  | { name: "markings" }
  | { name: "gestures" }
  | { name: "lights" }
  | { name: "favorites" }
  | { name: "rule"; code: string };

type NavKey = "home" | "signs" | "markings" | "gestures" | "lights" | "favorites";
const NAV_KEYS: Array<[NavKey, keyof Dict]> = [
  ["home", "theoryHome"],
  ["signs", "signs"],
  ["markings", "markings"],
  ["gestures", "gestures"],
  ["lights", "lights"],
  ["favorites", "favorites"]
];

export function TheoryArea({ onExit, initialView }: { onExit: () => void; initialView?: TheoryView }) {
  // TheoryArea unmounts when leaving the Theory tab, so useState(initialView) is enough to
  // open on a specific view (e.g. a rule) and default back to home on the next entry.
  const [view, setView] = useState<TheoryView>(initialView ?? { name: "home" });
  const [, setHistory] = useState<TheoryView[]>([]);
  const viewRef = useRef(view);
  useEffect(() => { viewRef.current = view; }, [view]);

  const [practice, setPractice] = useState<TheoryPracticeStart | null>(null);
  const [practiceBusy, setPracticeBusy] = useState(false);
  const [practiceError, setPracticeError] = useState<string | null>(null);
  const lastPractice = useRef<{ type: "article" | "sign"; id: string } | null>(null);

  const go = useCallback((v: TheoryView) => { setHistory((h) => [...h, viewRef.current]); setView(v); }, []);
  const navTop = useCallback((v: TheoryView) => { setHistory([]); setView(v); }, []);
  const back = useCallback(() => {
    setHistory((h) => {
      if (h.length === 0) { onExit(); return h; }
      setView(h[h.length - 1]);
      return h.slice(0, -1);
    });
  }, [onExit]);

  const startPractice = useCallback(async (type: "article" | "sign", id: string) => {
    lastPractice.current = { type, id };
    setPracticeError(null);
    setPracticeBusy(true);
    try {
      const s = await theoryApi.startPractice(type, id);
      setPractice(s);
    } catch (e) {
      setPracticeError(String((e as Error).message));
    } finally {
      setPracticeBusy(false);
    }
  }, []);
  const retryPractice = useCallback(() => {
    const lp = lastPractice.current;
    if (lp) void startPractice(lp.type, lp.id);
  }, [startPractice]);

  if (practice) return <TheoryPractice start={practice} onExit={() => setPractice(null)} />;
  if (practiceBusy) {
    return (
      <Screen>
        <AppBar title={t("practiceThis")} />
        <Card><Skeleton height={180} /><div style={{ height: 12 }} /><Skeleton height={44} /></Card>
      </Screen>
    );
  }
  if (practiceError) {
    return (
      <Screen>
        <AppBar title={t("practiceThis")} />
        <Card>
          <EmptyState icon={<IconAlert size={36} />} message={t("loadFailed")}
            action={
              <div className="ui-row" style={{ gap: 8 }}>
                <Button onClick={retryPractice}>{t("retry")}</Button>
                <Button variant="secondary" onClick={() => setPracticeError(null)}>{t("back")}</Button>
              </div>
            } />
        </Card>
      </Screen>
    );
  }

  const activeKey: NavKey | "" =
    view.name === "section" || view.name === "article" ? "home"
      : view.name === "sign" ? "signs"
        : view.name === "rule" ? ""
          : view.name;

  return (
    <Screen>
      <AppBar title={t("theoryHome")}
        right={<Button variant="ghost" onClick={back}>{t("back")}</Button>} />
      <div className="ui-chips" style={{ marginBottom: 12 }}>
        {NAV_KEYS.map(([key, labelKey]) => (
          <Chip key={key} active={activeKey === key} onClick={() => navTop({ name: key } as TheoryView)}>
            {t(labelKey)}
          </Chip>
        ))}
      </div>

      {view.name === "home" && (
        <TheoryHome
          onOpenSection={(slug) => go({ name: "section", slug })}
          onOpenResult={(r) => openResult(r, go)}
          onOpenCatalogue={(v) => navTop(v)} />
      )}
      {view.name === "section" && (
        <SectionView slug={view.slug} onOpenArticle={(slug) => go({ name: "article", slug })} />
      )}
      {view.name === "article" && (
        <ArticleView slug={view.slug} onPractice={(id) => startPractice("article", id)} />
      )}
      {view.name === "signs" && <SignsView onOpen={(code) => go({ name: "sign", code })} />}
      {view.name === "sign" && (
        <SignView code={view.code} onPractice={(id) => startPractice("sign", id)} />
      )}
      {view.name === "markings" && <MarkingsView />}
      {view.name === "gestures" && <GesturesView />}
      {view.name === "lights" && <LightsView />}
      {view.name === "favorites" && <FavoritesView />}
      {view.name === "rule" && (
        <RuleView code={view.code}
          onOpenArticle={(slug) => go({ name: "article", slug })}
          onOpenSign={(code) => go({ name: "sign", code })} />
      )}
    </Screen>
  );
}

function openResult(r: SearchResult, go: (v: TheoryView) => void) {
  if (r.type === "section" && r.slug) go({ name: "section", slug: r.slug });
  else if (r.type === "article" && r.slug) go({ name: "article", slug: r.slug });
  else if (r.type === "sign" && r.code) go({ name: "sign", code: r.code });
  else if (r.type === "rule" && r.code) go({ name: "rule", code: r.code });
  else if (r.type === "marking") go({ name: "markings" });
  else if (r.type === "gesture") go({ name: "gestures" });
  else if (r.type === "light") go({ name: "lights" });
}

// --------------------------------------------------------------------------- home
function TheoryHome({ onOpenSection, onOpenResult, onOpenCatalogue }: {
  onOpenSection: (slug: string) => void;
  onOpenResult: (r: SearchResult) => void;
  onOpenCatalogue: (v: TheoryView) => void;
}) {
  const sec = useFetch(() => theoryApi.sections(), []);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchNonce, setSearchNonce] = useState(0);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults(null);
      setSearchError(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    setSearchError(null);
    const id = setTimeout(() => {
      theoryApi.search(q)
        .then((r) => { setResults(r.results); setSearching(false); })
        .catch((e) => { setSearchError(String((e as Error).message)); setSearching(false); });
    }, 250);
    return () => clearTimeout(id);
  }, [q, searchNonce]);

  const catalogue: Array<[TheoryView, string, keyof Dict, keyof Dict | null]> = [
    [{ name: "signs" }, "🚸", "signs", "signsCatalogueHint"],
    [{ name: "markings" }, "🛣️", "markings", null],
    [{ name: "gestures" }, "🧍", "gestures", null],
    [{ name: "lights" }, "🚦", "lights", null]
  ];

  return (
    <div className="ui-stack">
      <input className="ui-input" placeholder={t("searchPlaceholder")} value={q}
        onChange={(e) => setQ(e.target.value)} />

      {results !== null || searching || searchError ? (
        <>
          {searching && <LoadOrError error={null} onRetry={() => setSearchNonce((n) => n + 1)} rows={3} />}
          {searchError && <LoadOrError error={searchError} onRetry={() => setSearchNonce((n) => n + 1)} />}
          {!searching && !searchError && results !== null && (
            results.length === 0 ? (
              <Card><EmptyState message={t("noResults")} /></Card>
            ) : (
              <div className="ui-stack ui-stack--sm">
                {results.map((r) => (
                  <ListRow key={`${r.type}-${r.id}`} title={r.title}
                    subtitle={r.subtitle ? `${resultTypeLabel(r.type)} · ${r.subtitle}` : resultTypeLabel(r.type)}
                    onClick={() => onOpenResult(r)} />
                ))}
              </div>
            )
          )}
        </>
      ) : (
        <>
          <div className="ui-stack ui-stack--sm">
            {catalogue.map(([target, emoji, titleKey, hintKey]) => (
              <ListRow key={titleKey} icon={<span style={{ fontSize: 20 }}>{emoji}</span>}
                title={t(titleKey)} subtitle={hintKey ? t(hintKey) : undefined}
                onClick={() => onOpenCatalogue(target)} />
            ))}
          </div>

          {!sec.data ? (
            <LoadOrError error={sec.error} onRetry={sec.reload} rows={4} />
          ) : sec.data.sections.length === 0 ? (
            <Card><EmptyState message={t("noData")} /></Card>
          ) : (
            <div className="ui-stack ui-stack--sm">
              {sec.data.sections.map((s: TheorySectionCard) => (
                <ListRow key={s.id} title={s.title} subtitle={s.subtitle || undefined}
                  right={s.progress
                    ? <Badge>{s.progress.viewed}/{s.progress.total}</Badge>
                    : undefined}
                  onClick={() => onOpenSection(s.slug)} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- section
function SectionView({ slug, onOpenArticle }: { slug: string; onOpenArticle: (slug: string) => void }) {
  const { data, error, reload } = useFetch<TheorySection>(() => theoryApi.section(slug), [slug]);
  if (!data) return <LoadOrError error={error} onRetry={reload} rows={4} />;
  return (
    <div className="ui-stack">
      <div>
        <h2 className="ui-h1">{data.title}</h2>
        {data.subtitle && <p className="ui-muted">{data.subtitle}</p>}
      </div>
      {data.articles.length === 0 ? (
        <Card><EmptyState message={t("noResults")} /></Card>
      ) : (
        <div className="ui-stack ui-stack--sm">
          {data.articles.map((a: TheoryArticleCard) => (
            <ListRow key={a.id} title={a.title} subtitle={a.summary || undefined}
              right={a.progress_state && a.progress_state !== "none"
                ? <Badge tone="accent">{a.progress_state}</Badge>
                : undefined}
              onClick={() => onOpenArticle(a.slug)} />
          ))}
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- article
function ArticleView({ slug, onPractice }: { slug: string; onPractice: (id: string) => void }) {
  const { data, error, reload } = useFetch<TheoryArticle>(() => theoryApi.article(slug), [slug]);
  if (!data) return <LoadOrError error={error} onRetry={reload} rows={5} />;
  return (
    <div className="ui-stack">
      <Card>
        <QuestionMedia url={data.hero_url} mediaType="image" alt={data.title} />
        <h2 className="ui-h1" style={{ marginTop: data.hero_url ? 12 : 0 }}>{data.title}</h2>
        {data.summary && <p className="ui-muted">{data.summary}</p>}
        <div style={{ marginTop: 12 }}>
          <FavButton targetType="article" targetId={data.id} />
        </div>
      </Card>

      <Card>
        <div className="theory-blocks">
          {data.blocks.map((b) => <Block key={b.id} block={b} />)}
        </div>
      </Card>

      {data.linked_question_count > 0 && (
        <Button block onClick={() => onPractice(data.id)}>
          {t("practiceThis")} ({data.linked_question_count})
        </Button>
      )}
      <ReportButton targetType="article" targetId={data.id} />
    </div>
  );
}

// --------------------------------------------------------------------------- signs
function SignsView({ onOpen }: { onOpen: (code: string) => void }) {
  const [family, setFamily] = useState("");
  const { data, error, reload } = useFetch(() => theoryApi.signs(family || undefined), [family]);
  return (
    <div className="ui-stack">
      <h2 className="ui-h1">{t("signs")}</h2>
      <div className="ui-chips">
        {FAMILIES.map(([key, labelKey]) => (
          <Chip key={key} active={family === key} onClick={() => setFamily(key)}>{t(labelKey)}</Chip>
        ))}
      </div>
      {!data ? (
        <LoadOrError error={error} onRetry={reload} rows={4} />
      ) : data.signs.length === 0 ? (
        <Card><EmptyState message={t("noResults")} /></Card>
      ) : (
        <div className="theory-grid">
          {data.signs.map((s: SignCard) => (
            <button key={s.id} className="theory-tile sign" onClick={() => onOpen(s.code)}>
              {s.media_url
                ? <img className="theory-sign-img" src={s.media_url} alt={s.name} loading="lazy" />
                : <div className="theory-sign-ph">{s.code}</div>}
              <strong>{s.code}</strong>
              <span className="muted">{s.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SignView({ code, onPractice }: { code: string; onPractice: (id: string) => void }) {
  const { data, error, reload } = useFetch<SignDetail>(() => theoryApi.sign(code), [code]);
  if (!data) return <LoadOrError error={error} onRetry={reload} rows={5} />;
  return (
    <div className="ui-stack">
      <Card>
        <QuestionMedia url={data.media_url} mediaType="image" alt={data.name} />
        <h2 className="ui-h1" style={{ marginTop: data.media_url ? 12 : 0 }}>{data.code} — {data.name}</h2>
        <div style={{ marginTop: 12 }}>
          <FavButton targetType="sign" targetId={data.id} />
        </div>
      </Card>

      <Card>
        <div className="ui-stack ui-stack--sm">
          <p><strong>{t("meaning")}:</strong> {data.meaning}</p>
          <p><strong>{t("whatToDo")}:</strong> {data.driver_action}</p>
          {data.important && <p><strong>{t("important")}:</strong> {data.important}</p>}
          {data.exam_trap && <p className="theory-callout warn">{t("commonMistake")}: {data.exam_trap}</p>}
          {data.memory_tip && <p className="theory-callout tip">{t("memoryTip")}: {data.memory_tip}</p>}
          {data.rules.map((r) => <RuleCard key={r.code} rule={r} />)}
        </div>
      </Card>

      {data.linked_question_count > 0 && (
        <Button block onClick={() => onPractice(data.id)}>
          {t("practiceThis")} ({data.linked_question_count})
        </Button>
      )}
      <ReportButton targetType="sign" targetId={data.id} />
    </div>
  );
}

// --------------------------------------------------------------------------- markings
function MarkingsView() {
  const [openId, setOpenId] = useState<string | null>(null);
  const { data, error, reload } = useFetch(() => theoryApi.markings(), []);
  if (openId) return <MarkingDetailView id={openId} onBack={() => setOpenId(null)} />;
  return (
    <div className="ui-stack">
      <h2 className="ui-h1">{t("markings")}</h2>
      {!data ? (
        <LoadOrError error={error} onRetry={reload} rows={4} />
      ) : data.markings.length === 0 ? (
        <Card><EmptyState message={t("noResults")} /></Card>
      ) : (
        <div className="theory-grid">
          {data.markings.map((m: MarkingCard) => (
            <button key={m.id} className="theory-tile" onClick={() => setOpenId(m.id)}>
              {m.media_url && <img className="theory-sign-img" src={m.media_url} alt={m.name} loading="lazy" />}
              <strong>{m.name}</strong><span className="muted">{m.group}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function MarkingDetailView({ id, onBack }: { id: string; onBack: () => void }) {
  const { data, error, reload } = useFetch<MarkingDetail>(() => theoryApi.marking(id), [id]);
  return (
    <div className="ui-stack">
      <Button variant="ghost" onClick={onBack}>{t("back")}</Button>
      {!data ? (
        <LoadOrError error={error} onRetry={reload} rows={4} />
      ) : (
        <>
          <Card>
            <QuestionMedia url={data.media_url} mediaType="image" alt={data.name} />
            <h2 className="ui-h1" style={{ marginTop: data.media_url ? 12 : 0 }}>{data.name}</h2>
            <div style={{ marginTop: 12 }}>
              <FavButton targetType="marking" targetId={data.id} />
            </div>
          </Card>
          <Card>
            <div className="ui-stack ui-stack--sm">
              <p><strong>{t("meaning")}:</strong> {data.meaning}</p>
              {data.can_cross && <p><strong>{t("canCross")}:</strong> {data.can_cross}</p>}
              {data.can_stop_park && <p><strong>{t("canStopPark")}:</strong> {data.can_stop_park}</p>}
              {data.conflict_rule && <p className="theory-callout warn">{t("conflictRule")}: {data.conflict_rule}</p>}
              {data.rules.map((r) => <RuleCard key={r.code} rule={r} />)}
            </div>
          </Card>
          <ReportButton targetType="marking" targetId={data.id} />
        </>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- gestures
function GesturesView() {
  const [openId, setOpenId] = useState<string | null>(null);
  const { data, error, reload } = useFetch(() => theoryApi.gestures(), []);
  if (openId) return <GestureDetailView id={openId} onBack={() => setOpenId(null)} />;
  return (
    <div className="ui-stack">
      <h2 className="ui-h1">{t("gestures")}</h2>
      {!data ? (
        <LoadOrError error={error} onRetry={reload} rows={4} />
      ) : data.gestures.length === 0 ? (
        <Card><EmptyState message={t("noResults")} /></Card>
      ) : (
        <div className="theory-grid">
          {data.gestures.map((g: GestureCard) => (
            <button key={g.id} className="theory-tile" onClick={() => setOpenId(g.id)}>
              {g.media_url && <img className="theory-sign-img" src={g.media_url} alt={g.name} loading="lazy" />}
              <strong>{g.name}</strong>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function GestureDetailView({ id, onBack }: { id: string; onBack: () => void }) {
  const { data, error, reload } = useFetch<GestureDetail>(() => theoryApi.gesture(id), [id]);
  return (
    <div className="ui-stack">
      <Button variant="ghost" onClick={onBack}>{t("back")}</Button>
      {!data ? (
        <LoadOrError error={error} onRetry={reload} rows={4} />
      ) : (
        <>
          <Card>
            {data.animation_url
              ? <QuestionMedia url={data.animation_url} mediaType="video" alt={data.name} />
              : <QuestionMedia url={data.media_url} mediaType="image" alt={data.name} />}
            <h2 className="ui-h1" style={{ marginTop: 12 }}>{data.name}</h2>
            <div style={{ marginTop: 12 }}>
              <FavButton targetType="gesture" targetId={data.id} />
            </div>
          </Card>
          <Card>
            <div className="ui-stack ui-stack--sm">
              <p><strong>{t("position")}:</strong> {data.position_desc}</p>
              <p className="theory-callout tip"><strong>{t("allowed")}:</strong> {data.allowed}</p>
              <p className="theory-callout warn"><strong>{t("forbidden")}:</strong> {data.forbidden}</p>
              {data.memory_tip && <p className="theory-callout tip">{t("memoryTip")}: {data.memory_tip}</p>}
              {data.rules.map((r) => <RuleCard key={r.code} rule={r} />)}
            </div>
          </Card>
          <ReportButton targetType="gesture" targetId={data.id} />
        </>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- lights
function LightsView() {
  const [openId, setOpenId] = useState<string | null>(null);
  const { data, error, reload } = useFetch(() => theoryApi.lights(), []);
  if (openId) return <LightDetailView id={openId} onBack={() => setOpenId(null)} />;
  return (
    <div className="ui-stack">
      <h2 className="ui-h1">{t("lights")}</h2>
      {!data ? (
        <LoadOrError error={error} onRetry={reload} rows={4} />
      ) : data.lights.length === 0 ? (
        <Card><EmptyState message={t("noResults")} /></Card>
      ) : (
        <div className="theory-grid">
          {data.lights.map((l: LightCard) => (
            <button key={l.id} className="theory-tile" onClick={() => setOpenId(l.id)}>
              {l.media_url && <img className="theory-sign-img" src={l.media_url} alt={l.title} loading="lazy" />}
              <strong>{l.title}</strong><span className="muted">{l.kind}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function LightDetailView({ id, onBack }: { id: string; onBack: () => void }) {
  const { data, error, reload } = useFetch<LightDetail>(() => theoryApi.light(id), [id]);
  return (
    <div className="ui-stack">
      <Button variant="ghost" onClick={onBack}>{t("back")}</Button>
      {!data ? (
        <LoadOrError error={error} onRetry={reload} rows={4} />
      ) : (
        <>
          <Card>
            <QuestionMedia url={data.media_url} mediaType="image" alt={data.title} />
            <h2 className="ui-h1" style={{ marginTop: data.media_url ? 12 : 0 }}>{data.title}</h2>
            <div style={{ marginTop: 12 }}>
              <FavButton targetType="light" targetId={data.id} />
            </div>
          </Card>
          <Card>
            <div className="ui-stack ui-stack--sm">
              <p><strong>{t("meaning")}:</strong> {data.meaning}</p>
              {data.movement_permitted && <p><strong>{t("movementPermitted")}:</strong> {data.movement_permitted}</p>}
              {data.direction_permitted && <p><strong>{t("directionPermitted")}:</strong> {data.direction_permitted}</p>}
              {data.exceptions && <p><strong>{t("exceptions")}:</strong> {data.exceptions}</p>}
              {data.typical_exam_situation && <p className="theory-callout example">{t("examSituation")}: {data.typical_exam_situation}</p>}
              {data.rules.map((r) => <RuleCard key={r.code} rule={r} />)}
            </div>
          </Card>
          <ReportButton targetType="light" targetId={data.id} />
        </>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- favorites
function FavoritesView() {
  const { data, error, reload } = useFetch(() => theoryApi.favorites(), []);
  const [removing, setRemoving] = useState<string | null>(null);
  const remove = async (favId: string) => {
    setRemoving(favId);
    try {
      await theoryApi.removeFavorite(favId);
      reload();
    } finally {
      setRemoving(null);
    }
  };
  return (
    <div className="ui-stack">
      <h2 className="ui-h1">{t("favorites")}</h2>
      {!data ? (
        <LoadOrError error={error} onRetry={reload} rows={3} />
      ) : data.favorites.length === 0 ? (
        <Card><EmptyState message={t("noFavorites")} /></Card>
      ) : (
        <div className="ui-stack ui-stack--sm">
          {data.favorites.map((f: FavoriteItem) => (
            <ListRow key={f.id} title={f.target_id} subtitle={f.target_type}
              right={
                <Button variant="secondary" disabled={removing === f.id}
                  onClick={() => remove(f.id)}>{t("removeFav")}</Button>
              } />
          ))}
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- rule (Practice -> Theory)
function RuleView({ code, onOpenArticle, onOpenSign }: {
  code: string;
  onOpenArticle: (slug: string) => void;
  onOpenSign: (code: string) => void;
}) {
  const { data, error, reload } = useFetch(() => theoryApi.byRule(code), [code]);
  if (!data) return <LoadOrError error={error} onRetry={reload} rows={4} />;
  const empty = data.articles.length === 0 && data.signs.length === 0;
  return (
    <div className="ui-stack">
      <Card>
        <h2 className="ui-h1">{t("rule")} — {data.rule.code}</h2>
        {data.rule.title && <p className="ui-muted">{data.rule.title}</p>}
        {data.rule.text && <p className="theory-text" style={{ marginTop: 8 }}>{data.rule.text}</p>}
      </Card>

      {empty ? (
        <Card><EmptyState message={t("ruleNoMaterial")} /></Card>
      ) : (
        <>
          <p className="ui-field-label">{t("ruleMaterials")}</p>
          {data.articles.length > 0 && (
            <div className="ui-stack ui-stack--sm">
              {data.articles.map((a: TheoryArticleCard) => (
                <ListRow key={a.id} title={a.title}
                  subtitle={a.summary ? `${t("articleKind")} · ${a.summary}` : t("articleKind")}
                  onClick={() => onOpenArticle(a.slug)} />
              ))}
            </div>
          )}
          {data.signs.length > 0 && (
            <div className="ui-stack ui-stack--sm">
              {data.signs.map((s: SignCard) => (
                <ListRow key={s.id}
                  icon={s.media_url
                    ? <img className="theory-sign-img" style={{ width: 40, height: 40 }} src={s.media_url} alt={s.name} loading="lazy" />
                    : undefined}
                  title={`${s.code} — ${s.name}`} subtitle={t("signs")}
                  onClick={() => onOpenSign(s.code)} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
