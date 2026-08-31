# 02 — Domain model

Adapted from the SATStudy SQLAlchemy models. Names are logical; final table names follow the
`snake_case` convention. Every entity has `id` (UUID string), `created_at`, `updated_at`
unless noted.

## Design principles baked into this model

- **One shared question bank.** Practice and mock exams use the same questions. No separate
  exam bank, no mock templates.
- **Immutable published content.** A `Question` is a stable container; its shown content
  lives in **immutable `QuestionVersion`** rows. A mock/practice attempt references the exact
  **version** the user saw, so historical attempts never change when content is edited later.
- **Translation-ready everywhere.** All human-readable text (question, options, rules, media
  alt) lives in per-language translation tables. v1 writes only `uz`.
- **Structured legal provenance.** Every publishable version links to one or more `Rule`
  versions; supporting research links are a separate structured list.
- **Media by reference, content-addressed, immutable.** Versions point to immutable media
  rows (addressed by content hash); replacing media means a new media row + new version.
- **Exam rules snapshotted** onto each `MockAttempt` from the single exam config.
- **Server is the only authority** for correctness, scoring, timers, and points. Correct
  answers/explanations are never sent to the client during a live mock (see
  [09-security.md](09-security.md)).

## Mapping from SATStudy

| SATStudy | prava-bot | Change |
| --- | --- | --- |
| `Section` (math/reading_writing) | `Category` (`B`; later `A`,`A1`,`C`,`D`) | replace |
| `Question` holds text + status | `Question` (container) + immutable `QuestionVersion` | split, version |
| text on question/option | translation tables keyed to **version** / option | split out |
| `QuestionImage` bytes-in-DB | `QuestionMedia` metadata + object storage + hash (immutable) | externalise |
| SPR (type-in) | removed | drop |
| `ExamTemplate`/routing/score | `MockAttempt` (single, pass/fail) | simplify |
| `QuestionAttempt` (global unique) | `PracticeAnswer` (repeatable) + `MockAnswer` (unique per attempt) | split + fix |
| — | `Rule` + `RuleTranslation` + `QuestionVersionRule` | add |
| — | `MistakeEntry`, `ContentReport`, ranking, readiness | add |
| allowlist admin only | `AdminRole` + per-endpoint authorization | add |

## Enums

- `Category`: `B` (v1); reserved `A`,`A1`,`C`,`D`.
- `Topic`: the 15 YHQ groups ([06-content-plan.md](06-content-plan.md)).
- `Language`: `uz` (v1); reserved `ru`.
- `MediaType`: `image`, `video`, `gif`.
- `VersionStatus`: `draft`, `needs_review`, `reviewed`, `published`, `needs_reverification`,
  `superseded`, `archived`.
- `MockStatus`: `in_progress`, `completed`, `abandoned`.
- `AdminRole`: `content_author`, `content_reviewer`, `admin`, `superadmin` (see
  [08-admin.md](08-admin.md) and [09-security.md](09-security.md)).

## Question container + immutable versions

```
Question                       # stable identity + mutable classification (not shown verbatim in exams)
  id
  category            Category  (index)
  topic               Topic     (index)
  subtopic            str?
  is_sign_question    bool = false      # eligible for the road-sign trainer
  current_version_id  -> QuestionVersion.id?   # the published version served to learners
  lifecycle_status    VersionStatus     # denormalised status of current work (for admin lists)
  created_by_user_id
  created_at / updated_at

QuestionVersion                # IMMUTABLE once published or used in any attempt
  id
  question_id         (index)
  version             int               # monotonic per question
  status              VersionStatus
  media_id            -> QuestionMedia.id?   # immutable, content-addressed
  difficulty          int               (1..3)
  ai_assisted         bool = false      # draft text was LLM-assisted (audit only)
  authored_by_user_id
  reviewed_by_user_id?
  approved_by_user_id?
  created_at
  published_at?
  verified_at?                          # human content verification date
  UNIQUE(question_id, version)
```

Immutability rule: once a `QuestionVersion` is `published` **or** referenced by any
`MockQuestion`/`PracticeAnswer`/`MockAnswer`, it must never be mutated. Editing published
content **creates a new `QuestionVersion`** (author → review → publish); publishing the new
version repoints `Question.current_version_id`. The prior version becomes `superseded` but is
retained for historical attempts. Attempts always resolve content through their stored
`question_version_id`.

## Content translations (keyed to version / option)

```
QuestionVersionTranslation
  id
  question_version_id  (index)
  language             Language
  prompt               text             # may be empty if media is self-contained
  short_explanation    text             # learner-friendly "remember this" (rule summary)
  UNIQUE(question_version_id, language)

AnswerOption
  id
  question_version_id  (index)          # options belong to a specific version
  position             int   (1..5)
  is_correct           bool             # language-neutral; never sent to client mid-mock

AnswerOptionTranslation
  id
  answer_option_id     (index)
  language             Language
  text                 text
  explanation          text             # why this option is right/wrong (shown after answering)
  UNIQUE(answer_option_id, language)
```

## Rule model (translation-ready legal provenance)

```
Rule                     # language-neutral legal identity
  id
  code                 str      # stable clause id, e.g. "YHQ:13.9"
  source_url           str
  source_document      str?
  effective_from       date?
  effective_to         date?
  verified_at          date
  version              int
  status               enum(active, superseded, repealed)

RuleTranslation
  id
  rule_id              (index)
  language             Language
  title                text?
  text                 text
  UNIQUE(rule_id, language)

QuestionVersionRule      # snapshot of which rule (and which rule version) a version relies on
  id
  question_version_id  (index)
  rule_id              (index)
  rule_version         int      # the Rule.version linked at authoring time (snapshot)
  UNIQUE(question_version_id, rule_id)
```

There is **no** `text_uz`/`title_uz` on `Rule`; text lives in `RuleTranslation`.

### Rule-change propagation

When a `Rule` is superseded/repealed (its `version` bumps or `status` changes), every
`QuestionVersion` linked via `QuestionVersionRule` to an **older** `rule_version` is flagged
`needs_reverification`. These surface prominently in the admin dashboard
([08-admin.md](08-admin.md)) and must be re-reviewed; they are not silently treated as
verified forever.

## Supporting sources (research provenance, distinct from legal basis)

```
QuestionVersionSource
  id
  question_version_id  (index)
  url                  str
  note                 str?
  kind                 enum(reference, diagram_source, media_source, other)
```

Distinction: **`Rule`/`QuestionVersionRule`** = the legal basis for the answer;
**`QuestionVersionSource`** = supporting provenance/research (formerly the informal
`source_refs`, now structured).

## Media (content-addressed, immutable; translation-ready alt text)

```
QuestionMedia            # immutable: identity == content hash
  id
  media_type           MediaType   (image | video | gif)
  content_type         str         (image/webp | video/mp4 | video/webm | image/gif)
  content_hash         str         # sha256 of stored bytes; part of the URL
  storage_key          str         # object-storage key (random, non-user-controlled)
  poster_hash          str?        # content hash of the video poster still
  width / height       int?
  duration_ms          int?
  byte_size            int

QuestionMediaTranslation
  id
  media_id             (index)
  language             Language
  alt_text             text
  UNIQUE(media_id, language)
```

- Bytes live in S3-compatible object storage (see [05-architecture.md](05-architecture.md));
  Postgres holds only metadata + hash + key.
- Serving URL is content-addressed: `/api/question-media/{media_id}/{content_hash}` → safe
  immutable caching; replacing media yields a new row/URL, so stale media is impossible.
- No `alt_text_uz` on the media entity; alt text is a translation.
- Media is language-neutral and shared across translations, except images with baked-in text
  (avoid).

## Practice (repeatable attempts, version-pinned)

```
PracticeSession
  id
  user_id              (index)
  category             Category
  topic                Topic?      # null => mixed
  source               enum(topic, mixed, mistakes, sign_trainer, diagnostic)
  started_at / ended_at?

PracticeAnswer
  id
  practice_session_id  (index)
  question_version_id                # exact content the user saw
  selected_option_id?
  is_correct           bool
  time_spent_seconds   int?
  attempted_at
```

No global `(user, question)` uniqueness — questions may recur across sessions (required for
mistakes review and ranking's unique-coverage logic, see [10-ranking.md](10-ranking.md)).

## Mock exam (self-contained, version-pinned snapshot)

```
MockAttempt
  id
  user_id              (index)
  category
  language                             # snapshot of user's language at start
  status               MockStatus
  started_at
  expires_at                           # = started_at + time_limit_seconds (server-authoritative)
  completed_at?
  exam_config_version  int             # snapshot of the single exam config
  question_count       int             # 20 (snapshot)
  time_limit_seconds   int             # 1500 (snapshot)
  pass_correct         int             # 18 (snapshot)
  correct_count        int?
  answered_count       int?
  passed               bool?
  result_json          json?           # per-topic breakdown, missed list, avg answer time

MockQuestion
  id
  mock_attempt_id      (index)
  question_version_id                  # PINNED to the immutable version at start
  position             int
  UNIQUE(mock_attempt_id, question_version_id)
  UNIQUE(mock_attempt_id, position)

MockAnswer
  id
  mock_attempt_id      (index)
  question_version_id
  selected_option_id?
  is_correct           bool?           # graded server-side at submit
  marked_for_review    bool = false
  answered_at?
  UNIQUE(mock_attempt_id, question_version_id)
```

Start-of-mock: select **20 random, unique, published** questions where `category` = user's
category and a `uz` `QuestionVersionTranslation` exists on the current version; **without
replacement**; pin each question's **current** `question_version_id` into `MockQuestion`.
Set `expires_at`, snapshot the exam config. Reopening never regenerates the set or deadline.
Historical review renders the pinned versions exactly as taken.

## Mistakes

```
MistakeEntry
  id
  user_id              (index)
  question_id                          # the container (mistakes track the question, not a version)
  first_missed_at / last_missed_at
  miss_count           int
  resolved             bool
  last_result          bool
  UNIQUE(user_id, question_id)
```

A wrong answer in practice or mock upserts the entry. Re-practice uses the question's current
version. v1 resolves on first correct re-answer; spaced repetition is v2.

## Content reports

```
ContentReport
  id
  user_id              (index)
  question_version_id                  # the exact version the reporter saw
  reason               enum(wrong_answer, unclear_explanation, image_problem, outdated_rule, typo, other)
  note                 text?
  status               enum(open, triaged, resolved, rejected)
  created_at
  resolved_by_user_id? / resolved_at?
```

Feeds the admin report queue ([08-admin.md](08-admin.md)).

## Users, roles, profiles

```
User                    # reused from SATStudy
  id, telegram_id, username, first_name, last_name, photo_url, last_seen_at
  admin_role  AdminRole?      # null for ordinary students; set for staff (allowlist-gated)

StudentProfile
  user_id (unique)
  display_name                # onboarding name
  ranking_name?               # name shown on leaderboards (defaults to display_name)
  show_on_ranking  bool = true
  category, language, target_exam_date?, daily_goal, timezone, onboarding_completed
```

Authorization: being in `ADMIN_TELEGRAM_IDS` is necessary but the effective capability is the
`admin_role`; every admin endpoint checks the role server-side (see
[09-security.md](09-security.md)). Version authorship/approval is recorded on
`QuestionVersion` (`authored_by`, `reviewed_by`, `approved_by`) plus `AdminAuditEvent` for
every state change (create/edit/review/publish/supersede/archive/import/bulk).

## Ranking, readiness (see dedicated specs)

- Ranking points and aggregates: [10-ranking.md](10-ranking.md) (server-computed;
  `UserPointsLedger` + periodic aggregates).
- Readiness: [07-readiness.md](07-readiness.md) (computed; optional `ReadinessSnapshot`).
  Both read from `PracticeAnswer`, `MockAttempt`/`MockAnswer`, `MistakeEntry`.

## Reused as-is from SATStudy

`AdminAuditEvent`; `Streak`, `StudentDailyStat`, `StudentWeeklyStat` (daily goals/streaks kept
and also feed ranking consistency). `NotificationEvent` deferred to v2.
