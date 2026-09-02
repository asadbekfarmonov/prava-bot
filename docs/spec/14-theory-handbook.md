# 14 — Theory / YHQ Handbook

A structured, visual **reference + learning system** inside the Mini App that complements
practice. Not a static article page: it is searchable, sectioned, image-heavy, versioned, and
bidirectionally linked to the question bank.

Uzbek section name: **`Nazariya`**. Mini App navigation becomes:

```
Home · Practice · Nazariya (Theory) · Mock exam · Progress · Ranking
```

The road-sign / marking / controller-gesture catalogues have their own structured entities and
are specified in [15-road-sign-catalogue.md](15-road-sign-catalogue.md); this file covers the
handbook framework (sections, articles, content blocks, progress, favorites, search, admin,
versioning, linkage).

## Non-negotiable content rules (verification)

- Every factual YHQ statement (sign numbers/names, speed limits, distances, controller
  gestures, prohibitions, post-accident steps) is **admin-authored and verification-required**,
  ultimately pointing to a verified source (current official Uzbekistan YHQ / LexUZ; other
  official government sources; an authoritative first-aid source for medical content).
- **Do not hard-code unverified facts.** v1 ships only clearly-marked **demo/original**
  placeholder theory content; real content is authored/verified in the admin studio. This
  mirrors the content-source-agnostic decision in
  [11-content-acquisition.md](11-content-acquisition.md).
- **First-aid** content must be grounded in an authoritative first-aid source and human/medically
  reviewed — never generated purely by an LLM. Separate **legal post-accident obligations**
  (YHQ) from **medical first aid**.
- Commercial prep sites may inform UX only; never copy their wording/content without a licence.
- Never claim theory content is the "official exam" material unless verified.

## Reuse first (do NOT duplicate)

Reuse existing infrastructure rather than inventing parallel concepts:
- **`Rule` / `RuleTranslation`** for legal basis and rule text (Theory links to rules; it does
  not restate the legal text in its own column).
- **`QuestionMedia` + `QuestionMediaTranslation`** and the **`MediaStorage`** adapter + the
  content-addressed `/api/media/{id}/{hash}` route for all images/animations/diagrams/posters.
- **Immutable-version + review lifecycle** pattern from questions
  ([02-domain-model.md](02-domain-model.md), [08-admin.md](08-admin.md)): Theory content is
  versioned the same way (`draft → needs_review → reviewed → published → needs_reverification →
  superseded/archived`) with `authored_by/reviewed_by/approved_by`, `AdminAuditEvent`, and the
  `needs_reverification` propagation when a linked `Rule` changes.
- **AdminRole** authorization, **content reports**, and the **search** approach.
- **Question** bank for Theory→Practice and Practice→Theory linkage; **PracticeAnswer/MockAnswer**
  performance drives the `mastered` progress state.
- Translation-table pattern (uz v1, ru-ready) and Uzbek copy conventions
  ([04-i18n.md](04-i18n.md)).

## Theory home screen

Category-based, searchable:

```
Nazariya
🔍 Qidirish...
Yo'l belgilari · Svetofor signallari · Regulirovshchik ishoralari · Yo'l chiziqlari ·
Chorrahalar va ustunlik · Manevr qilish · Tezlik · Quvib o'tish · To'xtash va to'xtab turish ·
Piyodalar va velosipedchilar · Temir yo'l kesishmalari · Avtomagistrallar ·
Transport vositasining texnik holati · Yo'lovchi va yuk tashish · Favqulodda vaziyatlar ·
Birinchi yordam
```

Sections reuse the `Topic` taxonomy where natural but Theory may be **finer-grained** (a topic
can have several sections/articles). Each section shows lightweight progress (below).

## Data model (theory framework)

Language-neutral base rows + translation tables; content is versioned and immutable once
published (same discriminator as questions: `published_at is not None ⇒ locked`).

```
TheorySection
  id
  slug                 (unique)
  topic                Topic?          # optional link to the shared taxonomy
  position             int
  icon_media_id        -> QuestionMedia.id?
  status               VersionStatus (published/… at the section level for visibility)
  # display text via TheorySectionTranslation(section_id, language, title, subtitle)

TheoryArticle                          # container (stable identity + classification)
  id
  section_id           (index)
  slug                 (unique within section)
  kind                 enum(lesson, reference, quick_ref, common_mistake)
  position             int
  is_sign_question?    n/a
  current_version_id   -> TheoryArticleVersion.id?
  lifecycle_status     VersionStatus

TheoryArticleVersion                   # IMMUTABLE once published/used
  id
  article_id           (index)
  version              int
  status               VersionStatus
  hero_media_id        -> QuestionMedia.id?
  ai_assisted          bool
  authored_by / reviewed_by? / approved_by?
  created_at / published_at? / verified_at?
  UNIQUE(article_id, version)

TheoryArticleTranslation
  id
  article_version_id   (index)
  language             Language
  title                text
  summary              text
  UNIQUE(article_version_id, language)

TheoryContentBlock                     # ordered structured blocks for a version (no raw HTML)
  id
  article_version_id   (index)
  position             int
  type                 enum(text, rule_callout, image, animation, diagram, comparison,
                            warning, memory_tip, table, example, practice_link)
  media_id             -> QuestionMedia.id?     # for image/animation/diagram
  rule_id              -> Rule.id?               # for rule_callout / linkage
  ref_question_id      -> Question.id?           # for practice_link
  data_json            json?                     # table cells, comparison pairs, etc. (structured)
  # human text via TheoryContentBlockTranslation(block_id, language, body)

TheoryArticleRule                      # article/version -> Rule(s), snapshot rule_version
  id
  article_version_id
  rule_id
  rule_version
  UNIQUE(article_version_id, rule_id)

TheoryArticleQuestionLink              # Theory -> Practice (which questions drill this article)
  id
  article_id
  question_id
  UNIQUE(article_id, question_id)
```

Notes:
- **No giant hard-coded frontend JSON** and **no arbitrary HTML** — content is structured blocks
  keyed to a version, rendered by a fixed set of safe React block components
  ([09-security.md](09-security.md) XSS: text nodes only).
- Legal text is **not** duplicated: `rule_callout` blocks + `TheoryArticleRule` reference the
  existing `Rule`/`RuleTranslation`.
- Road signs/markings/gestures are **separate structured catalogs**
  ([15-road-sign-catalogue.md](15-road-sign-catalogue.md)); an article may embed/link them but
  does not re-store them.

## Content blocks

Admins compose lessons from the block palette above (text, rule_callout, image, animation,
diagram, comparison, warning, memory_tip, table, example, practice_link). Lessons follow the
short pattern from the brief:

```
Rule → diagram → example → common mistake → practice button
```

Priority/intersection and manoeuvre lessons use `diagram`/`animation` blocks with vehicle-path
arrows (reusing the asset system in [11-content-acquisition.md](11-content-acquisition.md)).

## Theory ↔ Practice linkage (bidirectional)

- **Theory → Practice**: an article can show "Bu mavzu bo'yicha mashq — N ta savol
  [ Mashq qilish ]", starting a practice session over `TheoryArticleQuestionLink` questions
  (reusing the no-leak practice loop). Sign/marking/gesture detail pages have a **Mashq qilish**
  button that starts questions for that item.
- **Practice → Theory**: after a wrong answer, the explanation's rule (`Qoida: YHQ 13.9`) links
  to the Theory article(s)/catalog entries referencing that `Rule` (resolve via
  `TheoryArticleRule`/catalog rule links) — "[ Qoidani o'rganish ]".

## Progress inside Theory

Lightweight, per-user, and honest — **opening a page is not mastery**:

```
TheoryProgress
  id
  user_id
  article_id (or section_id / catalog-item ref)
  state       enum(viewed, practised, mastered)
  updated_at
  UNIQUE(user_id, target)
```

- `viewed`: opened the article/section.
- `practised`: answered ≥1 linked practice question.
- `mastered`: derived primarily from **question performance** on linked questions (e.g. recent
  accuracy ≥ threshold over enough linked questions) — computed server-side from
  `PracticeAnswer`/`MockAnswer`, not from page views. Threshold in domain config.
- Section rollups shown as `42 / 87 ko'rildi`, `6 / 10 mavzu`, etc.

## Favorites / saved

```
TheoryFavorite (user_id, target_type, target_id, created_at, UNIQUE(user_id,target_type,target_id))
```
Users save a sign / rule / lesson / marking / gesture; a **`Saqlanganlar`** screen lists them.
Cheap to include in v1; if it slips, it is a small follow-up (mark explicitly).

## "Common mistakes" layer

Optional `common_mistake` articles/blocks per section (`Ko'p uchraydigan xato`). Initially
admin-authored; later can surface analytics (most-missed rule/sign, most-confused options) from
the existing analytics — but **analytics never auto-changes the legal explanation**.

## Search (global Theory search)

One search box returning **mixed** results across sections, articles, and the catalogs:

```
"stop" →
  Yo'l belgisi 2.5 — …            (RoadSign)
  To'xtash va to'xtab turish       (TheorySection/Article)
  Stop line                        (RoadMarking)
  YHQ 6.13                         (Rule)
```

Matches: title/name, sign code, keywords, rule number/code, article body, and practical Uzbek
synonyms. Implementation: a normalized search index over published theory content + catalog
entries + rules (v1 may use SQL `ILIKE`/normalized-token matching consistent with the admin
question search; a fuller index can come later). Results are visibility-filtered (published
only for students).

## Admin Theory editor (extends the studio)

Add a Theory area to the admin studio ([08-admin.md](08-admin.md)):

```
Theory
├── Sections
├── Articles          (block editor + live mobile preview)
├── Road signs        (15-road-sign-catalogue.md)
├── Road markings
├── Controller gestures
└── Review queue
```

Admins can: create/edit articles, reorder blocks (drag/drop), attach images/animations (via the
media pipeline), add `rule_callout`/link Rules, link relevant Questions, preview the mobile UI,
set `verified_at`, send for review, and **publish a new immutable version**. Same
reviewer/audit/versioning/roles as questions. Editing a published article forks a new version.
Publishing repoints `current_version_id`. Theory content reports reuse the `ContentReport`
mechanism (extend the target to theory entities).

## Versioning & re-verification

Theory obeys the same provenance/versioning as questions. When a linked **`Rule`** is
superseded/repealed, every `TheoryArticleVersion` (and catalog entry) linked via
`TheoryArticleRule` to an older `rule_version` flips to **`needs_reverification`** and appears in
the admin review queue. Old legal explanations are never left silently active.

## Offline / performance (Telegram Mini App on mobile)

- Lazy-load images/animations; never download the whole sign/media library on first launch.
- Media is immutable + content-addressed → cache aggressively.
- Paginate/section the data (section list first; article/blocks on demand).
- Versioned static text can be cached aggressively.

## Design

Theory looks like a modern, friendly **driving handbook**: very visual, large sign/diagram
presentation, short readable explanations, clear typography, mobile-first, consistent
iconography, easy toggling between reference and practice. This is intentionally **distinct from
the plain exam-mode UI** ([12-ui-exam-mode.md](12-ui-exam-mode.md)), which stays test-like.

## Implementation plan (per steering §33)

1. **New tables/models**: `TheorySection`(+Translation), `TheoryArticle` +
   `TheoryArticleVersion`(+Translation), `TheoryContentBlock`(+Translation), `TheoryArticleRule`,
   `TheoryArticleQuestionLink`, `TheoryProgress`, `TheoryFavorite`; catalog entities in
   [15-road-sign-catalogue.md](15-road-sign-catalogue.md) (`RoadSign`(+Translation),
   `RoadMarking`(+Translation), `ControllerGesture`(+Translation), `TrafficLightState`(+Translation)).
   New migration **0005**.
2. **Reused existing models**: `Rule`/`RuleTranslation`, `QuestionMedia`/`QuestionMediaTranslation`
   + `MediaStorage`, `Question` (+ practice/mock answers for `mastered`), `ContentReport`,
   `AdminRole`, versioning/review pattern, i18n translation pattern.
3. **API endpoints**: student — `GET /api/theory/sections`, `GET /api/theory/sections/{slug}`,
   `GET /api/theory/articles/{slug}`, `GET /api/theory/search?q=`, `GET /api/theory/signs`
   (+filters), `GET /api/theory/signs/{code}`, markings/gestures/lights equivalents,
   `POST /api/theory/{target}/progress` (view/derived), `GET/POST/DELETE /api/theory/favorites`,
   Theory→Practice start (reuse practice session with an article-linked question source),
   Practice→Theory resolve-by-rule; admin — CRUD + review/publish for sections/articles/blocks
   and catalogs under `/api/admin/theory/*` (role-gated). All per-user resources IDOR-safe;
   student endpoints return published content only; **no answer leak** anywhere Theory embeds
   questions.
4. **Frontend routes/components**: a `Nazariya` tab; Theory home (sections + search), section
   page, article renderer (safe block components), sign catalogue (grid + filters + detail),
   markings, controller gestures (visual, optional animation), traffic-lights guide,
   quick-reference, favorites (`Saqlanganlar`), and the Theory↔Practice buttons. Friendly visual
   design, mobile-first, lazy media.
5. **Admin changes**: Theory area (Sections/Articles/Signs/Markings/Gestures/Review queue) with a
   block editor + live mobile preview, rule/question linking, versioned publish, reports.
6. **Migrations**: single new **0005** on top of 0004; additive; downgrade defined; applies
   cleanly on startup.
7. **Tests** (see §below and [15](15-road-sign-catalogue.md)): navigation; catalogue
   filtering; global search; Rule links; Theory→Practice and Practice→Theory; multilingual-ready
   schema; admin author/review/publish workflow; immutable versions; Rule-change →
   needs_reverification; unauthorized admin access; stored-XSS protection (blocks render inert);
   media access; progress states (view vs mastered); favorites; and key mobile e2e.

## Tests (acceptance)

Cover: theory navigation; sign catalogue filtering; search returns mixed content; rule links;
Theory→Practice starts linked questions with no answer leak; Practice→Theory opens the right
article by rule; translation-ready schema; admin author/review/publish + immutable versioning;
Rule change → needs_reverification propagation to theory; non-admin blocked from admin theory
endpoints (403); stored-XSS payload in a block renders inert; media access via content-addressed
route; progress distinguishes viewed/practised/mastered (mastery needs question performance, not
page views); favorites add/list/remove; mobile e2e for signs + one lesson.
