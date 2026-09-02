import { useCallback, useEffect, useState } from "react";
import { api, theoryApi } from "./api";
import { t } from "./i18n/uz";
import { QuestionMedia } from "./ui/components";
import type {
  AnswerResult,
  FavoriteItem,
  GestureCard,
  GestureDetail,
  LightCard,
  LightDetail,
  MarkingCard,
  MarkingDetail,
  NextQuestion,
  SearchResult,
  SignCard,
  SignDetail,
  TheoryArticle,
  TheoryBlock,
  TheorySection,
  TheorySectionCard,
  TheoryPracticeStart
} from "./types";

const FAMILIES: Array<[string, string]> = [
  ["", "allFamilies"],
  ["warning", "familyWarning"],
  ["priority", "familyPriority"],
  ["prohibitory", "familyProhibitory"],
  ["mandatory", "familyMandatory"],
  ["information", "familyInformation"],
  ["service", "familyService"],
  ["additional_plate", "familyAdditionalPlate"]
];

// Lazy-loaded media: <img loading="lazy"> / <video preload="metadata">. Never the whole
// library up front.
function Media({ url, alt }: { url: string | null; alt: string }) {
  if (!url) return null;
  const isVideo = /\.(mp4|webm)$/i.test(url);
  if (isVideo) {
    return <video className="theory-media" src={url} controls preload="metadata" playsInline />;
  }
  return <img className="theory-media" src={url} alt={alt} loading="lazy" />;
}

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

function FavButton({ targetType, targetId }: { targetType: string; targetId: string }) {
  const [saved, setSaved] = useState(false);
  const [favId, setFavId] = useState<string | null>(null);
  const toggle = async () => {
    if (saved && favId) {
      await theoryApi.removeFavorite(favId);
      setSaved(false);
      setFavId(null);
    } else {
      const r = await theoryApi.addFavorite(targetType, targetId);
      setSaved(true);
      setFavId(r.id);
    }
  };
  return (
    <button className="secondary" onClick={toggle}>
      {saved ? `★ ${t("saved")}` : `☆ ${t("save2")}`}
    </button>
  );
}

// A small in-Theory practice runner reusing the no-leak loop.
function TheoryPractice({ start, onExit }: { start: TheoryPracticeStart; onExit: () => void }) {
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const q: NextQuestion | undefined = start.questions[index];

  async function submit() {
    if (!q || !selected) return;
    const r = await api.submitAnswer(start.session_id, q.question_id, selected);
    setResult(r);
  }
  function next() {
    setResult(null);
    setSelected(null);
    setIndex((i) => i + 1);
  }

  if (!q) {
    return (
      <div className="card theory">
        <p>{t("noResults")}</p>
        <button className="secondary" onClick={onExit}>{t("back")}</button>
      </div>
    );
  }
  return (
    <div className="card theory">
      <button className="secondary" onClick={onExit}>{t("back")}</button>
      <p className="muted">{index + 1} / {start.questions_total}</p>
      <h1>{q.prompt}</h1>
      {q.media && <QuestionMedia media={q.media} />}
      {q.options.map((o) => {
        let cls = "option";
        if (result) {
          if (o.id === result.correct_option_id) cls += " correct";
          else if (o.id === selected) cls += " wrong";
        } else if (o.id === selected) cls += " selected";
        const graded = result?.options.find((g) => g.id === o.id);
        return (
          <div key={o.id}>
            <button className={cls} disabled={!!result} onClick={() => setSelected(o.id)}>{o.text}</button>
            {graded && <div className="explain">{graded.explanation}</div>}
          </div>
        );
      })}
      {!result ? (
        <button onClick={submit} disabled={!selected}>{t("submit")}</button>
      ) : (
        <>
          <p><strong>{result.is_correct ? t("correct") : t("incorrect")}</strong></p>
          {result.rule && (
            <div className="rule"><strong>{t("rule")}: {result.rule.code}</strong>
              <p className="explain">{result.rule.text}</p></div>
          )}
          <button onClick={next}>{t("next")}</button>
        </>
      )}
    </div>
  );
}

type View =
  | { name: "home" }
  | { name: "section"; slug: string }
  | { name: "article"; slug: string }
  | { name: "signs" }
  | { name: "sign"; code: string }
  | { name: "markings" }
  | { name: "gestures" }
  | { name: "lights" }
  | { name: "favorites" };

export function TheoryArea({ onExit }: { onExit: () => void }) {
  const [view, setView] = useState<View>({ name: "home" });
  const [practice, setPractice] = useState<TheoryPracticeStart | null>(null);

  const startPractice = useCallback(async (type: "article" | "sign", id: string) => {
    try {
      const s = await theoryApi.startPractice(type, id);
      setPractice(s);
    } catch (e) {
      alert(String((e as Error).message));
    }
  }, []);

  if (practice) return <TheoryPractice start={practice} onExit={() => setPractice(null)} />;

  const nav = (
    <div className="theory-tabs">
      <button className="secondary" onClick={() => setView({ name: "home" })}>{t("theoryHome")}</button>
      <button className="secondary" onClick={() => setView({ name: "signs" })}>{t("signs")}</button>
      <button className="secondary" onClick={() => setView({ name: "markings" })}>{t("markings")}</button>
      <button className="secondary" onClick={() => setView({ name: "gestures" })}>{t("gestures")}</button>
      <button className="secondary" onClick={() => setView({ name: "lights" })}>{t("lights")}</button>
      <button className="secondary" onClick={() => setView({ name: "favorites" })}>{t("favorites")}</button>
    </div>
  );

  return (
    <div className="theory-wrap">
      <div className="card theory">
        <button className="secondary" onClick={onExit}>{t("backHome")}</button>
        {nav}
      </div>
      {view.name === "home" && (
        <TheoryHome
          onOpenSection={(slug) => setView({ name: "section", slug })}
          onOpenResult={(r) => openResult(r, setView)}
          onOpenCatalogue={(name) => setView({ name } as View)}
        />
      )}
      {view.name === "section" && (
        <SectionView slug={view.slug} onOpenArticle={(slug) => setView({ name: "article", slug })} />
      )}
      {view.name === "article" && (
        <ArticleView slug={view.slug} onPractice={(id) => startPractice("article", id)} />
      )}
      {view.name === "signs" && <SignsView onOpen={(code) => setView({ name: "sign", code })} />}
      {view.name === "sign" && (
        <SignView code={view.code} onPractice={(id) => startPractice("sign", id)} />
      )}
      {view.name === "markings" && <MarkingsView />}
      {view.name === "gestures" && <GesturesView />}
      {view.name === "lights" && <LightsView />}
      {view.name === "favorites" && <FavoritesView />}
    </div>
  );
}

function openResult(r: SearchResult, setView: (v: View) => void) {
  if (r.type === "section" && r.slug) setView({ name: "section", slug: r.slug });
  else if (r.type === "article" && r.slug) setView({ name: "article", slug: r.slug });
  else if (r.type === "sign" && r.code) setView({ name: "sign", code: r.code });
  else if (r.type === "marking") setView({ name: "markings" });
  else if (r.type === "gesture") setView({ name: "gestures" });
  else if (r.type === "light") setView({ name: "lights" });
}

function TheoryHome({
  onOpenSection,
  onOpenResult,
  onOpenCatalogue
}: {
  onOpenSection: (slug: string) => void;
  onOpenResult: (r: SearchResult) => void;
  onOpenCatalogue: (name: "signs" | "markings" | "gestures" | "lights") => void;
}) {
  const [sections, setSections] = useState<TheorySectionCard[]>([]);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);

  useEffect(() => {
    theoryApi.sections().then((r) => setSections(r.sections)).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults(null);
      return;
    }
    const id = setTimeout(() => {
      theoryApi.search(q).then((r) => setResults(r.results)).catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(id);
  }, [q]);

  return (
    <div className="card theory">
      <h1>{t("theoryHome")}</h1>
      <input placeholder={t("searchPlaceholder")} value={q} onChange={(e) => setQ(e.target.value)} />
      {results !== null ? (
        <div className="theory-search-results">
          {results.length === 0 && <p className="muted">{t("noResults")}</p>}
          {results.map((r) => (
            <button key={`${r.type}-${r.id}`} className="secondary theory-result" onClick={() => onOpenResult(r)}>
              <span className="theory-badge">{r.type}</span> {r.title}
              {r.subtitle && <span className="muted"> · {r.subtitle}</span>}
            </button>
          ))}
        </div>
      ) : (
        <>
          <div className="theory-grid">
            <button className="theory-tile" onClick={() => onOpenCatalogue("signs")}>
              <strong>🚸 {t("signs")}</strong>
              <span className="muted">{t("signsCatalogueHint")}</span>
            </button>
            <button className="theory-tile" onClick={() => onOpenCatalogue("markings")}>
              <strong>🛣️ {t("markings")}</strong>
            </button>
            <button className="theory-tile" onClick={() => onOpenCatalogue("gestures")}>
              <strong>🧍 {t("gestures")}</strong>
            </button>
            <button className="theory-tile" onClick={() => onOpenCatalogue("lights")}>
              <strong>🚦 {t("lights")}</strong>
            </button>
          </div>
          <div className="theory-list">
            {sections.map((s) => (
              <button key={s.id} className="theory-tile" onClick={() => onOpenSection(s.slug)}>
                <strong>{s.title}</strong>
                {s.subtitle && <span className="muted">{s.subtitle}</span>}
                {s.progress && (
                  <span className="muted">{s.progress.viewed} / {s.progress.total} {t("viewed")}</span>
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function SectionView({ slug, onOpenArticle }: { slug: string; onOpenArticle: (slug: string) => void }) {
  const [section, setSection] = useState<TheorySection | null>(null);
  useEffect(() => {
    theoryApi.section(slug).then(setSection).catch(() => undefined);
  }, [slug]);
  if (!section) return <div className="card theory"><p>{t("loading")}</p></div>;
  return (
    <div className="card theory">
      <h1>{section.title}</h1>
      {section.subtitle && <p className="muted">{section.subtitle}</p>}
      <div className="theory-list">
        {section.articles.map((a) => (
          <button key={a.id} className="theory-tile" onClick={() => onOpenArticle(a.slug)}>
            <strong>{a.title}</strong>
            {a.summary && <span className="muted">{a.summary}</span>}
            {a.progress_state && a.progress_state !== "none" && (
              <span className="theory-badge">{a.progress_state}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

function ArticleView({ slug, onPractice }: { slug: string; onPractice: (id: string) => void }) {
  const [article, setArticle] = useState<TheoryArticle | null>(null);
  useEffect(() => {
    theoryApi.article(slug).then(setArticle).catch(() => undefined);
  }, [slug]);
  if (!article) return <div className="card theory"><p>{t("loading")}</p></div>;
  return (
    <div className="card theory">
      <h1>{article.title}</h1>
      {article.summary && <p className="muted">{article.summary}</p>}
      <Media url={article.hero_url} alt={article.title} />
      <FavButton targetType="article" targetId={article.id} />
      <div className="theory-blocks">
        {article.blocks.map((b) => <Block key={b.id} block={b} />)}
      </div>
      {article.linked_question_count > 0 && (
        <button onClick={() => onPractice(article.id)}>
          {t("practiceThis")} ({article.linked_question_count})
        </button>
      )}
    </div>
  );
}

function SignsView({ onOpen }: { onOpen: (code: string) => void }) {
  const [signs, setSigns] = useState<SignCard[]>([]);
  const [family, setFamily] = useState("");
  useEffect(() => {
    theoryApi.signs(family || undefined).then((r) => setSigns(r.signs)).catch(() => undefined);
  }, [family]);
  return (
    <div className="card theory">
      <h1>{t("signs")}</h1>
      <div className="theory-tabs">
        {FAMILIES.map(([key, label]) => (
          <button key={key} className={"secondary" + (family === key ? " marked" : "")} onClick={() => setFamily(key)}>
            {t(label as never)}
          </button>
        ))}
      </div>
      <div className="theory-grid">
        {signs.map((s) => (
          <button key={s.id} className="theory-tile sign" onClick={() => onOpen(s.code)}>
            {s.media_url ? <img className="theory-sign-img" src={s.media_url} alt={s.name} loading="lazy" /> : <div className="theory-sign-ph">{s.code}</div>}
            <strong>{s.code}</strong>
            <span className="muted">{s.name}</span>
          </button>
        ))}
        {signs.length === 0 && <p className="muted">{t("noResults")}</p>}
      </div>
    </div>
  );
}

function SignView({ code, onPractice }: { code: string; onPractice: (id: string) => void }) {
  const [sign, setSign] = useState<SignDetail | null>(null);
  useEffect(() => {
    theoryApi.sign(code).then(setSign).catch(() => undefined);
  }, [code]);
  if (!sign) return <div className="card theory"><p>{t("loading")}</p></div>;
  return (
    <div className="card theory">
      <Media url={sign.media_url} alt={sign.name} />
      <h1>{sign.code} — {sign.name}</h1>
      <FavButton targetType="sign" targetId={sign.id} />
      <p><strong>{t("meaning")}:</strong> {sign.meaning}</p>
      <p><strong>{t("whatToDo")}:</strong> {sign.driver_action}</p>
      {sign.important && <p><strong>{t("important")}:</strong> {sign.important}</p>}
      {sign.exam_trap && <p className="theory-callout warn">{t("commonMistake")}: {sign.exam_trap}</p>}
      {sign.memory_tip && <p className="theory-callout tip">{t("memoryTip")}: {sign.memory_tip}</p>}
      {sign.rules.map((r) => (
        <div key={r.code} className="rule"><strong>{t("rule")}: {r.code}</strong><p className="explain">{r.text}</p></div>
      ))}
      {sign.linked_question_count > 0 && (
        <button onClick={() => onPractice(sign.id)}>{t("practiceThis")} ({sign.linked_question_count})</button>
      )}
    </div>
  );
}

function MarkingsView() {
  const [items, setItems] = useState<MarkingCard[]>([]);
  const [detail, setDetail] = useState<MarkingDetail | null>(null);
  useEffect(() => { theoryApi.markings().then((r) => setItems(r.markings)).catch(() => undefined); }, []);
  if (detail) {
    return (
      <div className="card theory">
        <button className="secondary" onClick={() => setDetail(null)}>{t("back")}</button>
        <Media url={detail.media_url} alt={detail.name} />
        <h1>{detail.name}</h1>
        <FavButton targetType="marking" targetId={detail.id} />
        <p><strong>{t("meaning")}:</strong> {detail.meaning}</p>
        {detail.can_cross && <p><strong>{t("canCross")}:</strong> {detail.can_cross}</p>}
        {detail.can_stop_park && <p><strong>{t("canStopPark")}:</strong> {detail.can_stop_park}</p>}
        {detail.conflict_rule && <p className="theory-callout warn">{t("conflictRule")}: {detail.conflict_rule}</p>}
        {detail.rules.map((r) => <div key={r.code} className="rule"><strong>{r.code}</strong><p className="explain">{r.text}</p></div>)}
      </div>
    );
  }
  return (
    <div className="card theory">
      <h1>{t("markings")}</h1>
      <div className="theory-grid">
        {items.map((m) => (
          <button key={m.id} className="theory-tile" onClick={() => theoryApi.marking(m.id).then(setDetail)}>
            {m.media_url && <img className="theory-sign-img" src={m.media_url} alt={m.name} loading="lazy" />}
            <strong>{m.name}</strong><span className="muted">{m.group}</span>
          </button>
        ))}
        {items.length === 0 && <p className="muted">{t("noResults")}</p>}
      </div>
    </div>
  );
}

function GesturesView() {
  const [items, setItems] = useState<GestureCard[]>([]);
  const [detail, setDetail] = useState<GestureDetail | null>(null);
  useEffect(() => { theoryApi.gestures().then((r) => setItems(r.gestures)).catch(() => undefined); }, []);
  if (detail) {
    return (
      <div className="card theory">
        <button className="secondary" onClick={() => setDetail(null)}>{t("back")}</button>
        {detail.animation_url ? <Media url={detail.animation_url} alt={detail.name} /> : <Media url={detail.media_url} alt={detail.name} />}
        <h1>{detail.name}</h1>
        <FavButton targetType="gesture" targetId={detail.id} />
        <p><strong>{t("position")}:</strong> {detail.position_desc}</p>
        <p className="theory-callout tip"><strong>{t("allowed")}:</strong> {detail.allowed}</p>
        <p className="theory-callout warn"><strong>{t("forbidden")}:</strong> {detail.forbidden}</p>
        {detail.memory_tip && <p className="theory-callout tip">{t("memoryTip")}: {detail.memory_tip}</p>}
        {detail.rules.map((r) => <div key={r.code} className="rule"><strong>{r.code}</strong><p className="explain">{r.text}</p></div>)}
      </div>
    );
  }
  return (
    <div className="card theory">
      <h1>{t("gestures")}</h1>
      <div className="theory-grid">
        {items.map((g) => (
          <button key={g.id} className="theory-tile" onClick={() => theoryApi.gesture(g.id).then(setDetail)}>
            {g.media_url && <img className="theory-sign-img" src={g.media_url} alt={g.name} loading="lazy" />}
            <strong>{g.name}</strong>
          </button>
        ))}
        {items.length === 0 && <p className="muted">{t("noResults")}</p>}
      </div>
    </div>
  );
}

function LightsView() {
  const [items, setItems] = useState<LightCard[]>([]);
  const [detail, setDetail] = useState<LightDetail | null>(null);
  useEffect(() => { theoryApi.lights().then((r) => setItems(r.lights)).catch(() => undefined); }, []);
  if (detail) {
    return (
      <div className="card theory">
        <button className="secondary" onClick={() => setDetail(null)}>{t("back")}</button>
        <Media url={detail.media_url} alt={detail.title} />
        <h1>{detail.title}</h1>
        <FavButton targetType="light" targetId={detail.id} />
        <p><strong>{t("meaning")}:</strong> {detail.meaning}</p>
        {detail.movement_permitted && <p><strong>{t("movementPermitted")}:</strong> {detail.movement_permitted}</p>}
        {detail.direction_permitted && <p><strong>{t("directionPermitted")}:</strong> {detail.direction_permitted}</p>}
        {detail.exceptions && <p><strong>{t("exceptions")}:</strong> {detail.exceptions}</p>}
        {detail.typical_exam_situation && <p className="theory-callout example">{t("examSituation")}: {detail.typical_exam_situation}</p>}
        {detail.rules.map((r) => <div key={r.code} className="rule"><strong>{r.code}</strong><p className="explain">{r.text}</p></div>)}
      </div>
    );
  }
  return (
    <div className="card theory">
      <h1>{t("lights")}</h1>
      <div className="theory-grid">
        {items.map((l) => (
          <button key={l.id} className="theory-tile" onClick={() => theoryApi.light(l.id).then(setDetail)}>
            {l.media_url && <img className="theory-sign-img" src={l.media_url} alt={l.title} loading="lazy" />}
            <strong>{l.title}</strong><span className="muted">{l.kind}</span>
          </button>
        ))}
        {items.length === 0 && <p className="muted">{t("noResults")}</p>}
      </div>
    </div>
  );
}

function FavoritesView() {
  const [items, setItems] = useState<FavoriteItem[]>([]);
  const load = useCallback(() => {
    theoryApi.favorites().then((r) => setItems(r.favorites)).catch(() => undefined);
  }, []);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="card theory">
      <h1>{t("favorites")}</h1>
      {items.length === 0 && <p className="muted">{t("noFavorites")}</p>}
      <div className="theory-list">
        {items.map((f) => (
          <div key={f.id} className="theory-fav">
            <span className="theory-badge">{f.target_type}</span>
            <span>{f.target_id}</span>
            <button className="secondary" onClick={async () => { await theoryApi.removeFavorite(f.id); load(); }}>
              {t("removeFav")}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
