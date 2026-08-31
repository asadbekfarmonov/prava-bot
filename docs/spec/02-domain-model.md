# 02 — Domain model

Adapted from the SATStudy SQLAlchemy models. Names are logical; final table names follow
the existing `snake_case` convention. Every entity has `id` (UUID string), `created_at`,
`updated_at` unless noted.

## Design principles baked into this model

- **One shared question bank.** Practice and mock exams use the **same `Question`**
  records. There is no separate exam bank and **no mock templates**.
- **Translation-ready now.** Language-specific text lives in translation tables so Russian
  can be added later without a major migration. v1 writes only `uz` rows.
- **Structured legal provenance.** Every publishable question links to one or more `Rule`
  records; free-form strings are not the legal foundation.
- **Media by reference.** Questions reference a `QuestionMedia` row; bytes live in object
  storage, addressed by content hash (see [05-architecture.md](05-architecture.md)).
- **Exam rules are snapshotted** onto each `MockAttempt` from the single exam config.

## Mapping from SATStudy

| SATStudy | prava-bot | Change |
| --- | --- | --- |
| `Section` enum (math/reading_writing) | `Category` enum (`B`; later `A`,`A1`,`C`,`D`) | replace |
| `Question.topic`/`.skill` free text | `Topic` (controlled) + `subtopic` + `Rule` links | tighten |
| text on `Question`/`AnswerOption` | `QuestionTranslation` / `AnswerOptionTranslation` | split out |
| `QuestionImage` bytes-in-DB | `QuestionMedia` metadata + object-storage + hash | extend/externalise |
| SPR (type-in) | **removed** | drop |
| `ExamTemplate` (adaptive, 4 modules) + `ExamTemplateQuestion` | **removed** | drop |
| `ExamAttempt` + adaptive routing + 400–1600 score | `MockAttempt` (single, pass/fail) | simplify |
| `QuestionAttempt` (global unique per user+question) | `PracticeAnswer` (repeatable) + `MockAnswer` (unique per attempt) | split + fix |
| — | `Rule`, `QuestionRule` | add |
| — | `MistakeEntry` | add |
| — | readiness (computed; optional `ReadinessSnapshot`) | add |

## Enums

- `Category`: `B` (v1). Reserved: `A`, `A1`, `C`, `D`.
- `Topic`: the 15 YHQ groups from [06-content-plan.md](06-content-plan.md).
- `QuestionStatus`: `draft`, `reviewed`, `published`, `archived`.
- `MediaType`: `image`, `video`, `gif`.
- `MockStatus`: `in_progress`, `completed`, `abandoned`.
- `Language`: `uz` (v1). Reserved: `ru`.

## Question and content (translation-ready)

```
Question
  id
  category            Category       (index)
  topic               Topic          (index)
  subtopic            str?
  status              QuestionStatus  (index)
  media_id            -> QuestionMedia.id?   (0 or 1 media item, language-neutral)
  difficulty          int            (1..3; drives mock variety, NOT an exam blueprint)
  is_sign_question    bool = false   # true => eligible for the road-sign trainer
  content_version     int  = 1
  verified_at         date?
  created_by_user_id / updated_by_user_id

QuestionTranslation
  id
  question_id         (index)
  language            Language
  prompt              text           # may be empty if the media is self-contained
  short_explanation   text           # shown in practice + review (rule summary)
  UNIQUE(question_id, language)

AnswerOption
  id
  question_id         (index)
  position            int            (1..5)
  is_correct          bool           # language-neutral (correctness never varies by language)

AnswerOptionTranslation
  id
  answer_option_id    (index)
  language            Language
  text                text
  explanation         text           # why this option is right/wrong (shown after answering)
  UNIQUE(answer_option_id, language)
```

Publish validation (backend), evaluated against the user-facing language(s) present:
- media present **or** non-empty `prompt` in the primary language;
- **2–5** `AnswerOption` rows; **exactly one** `is_correct`;
- every option has a non-empty `explanation` in the primary language;
- **at least one `QuestionRule`** (verified provenance) — see Rule model;
- `short_explanation` present in the primary language.

v1 primary language is `uz`. Russian rows are simply absent until v2.

## Rule model (legal provenance)

```
Rule
  id
  code                str            # stable clause id, e.g. "YHQ:13.9"
  title               str?
  text_uz             text           # the rule text (uz v1; ru added later, see i18n)
  source_url          str
  source_document     str?
  effective_from      date?
  effective_to        date?
  verified_at         date
  version             int
  status              enum(active, superseded, repealed)

QuestionRule
  id
  question_id         (index)
  rule_id             (index)
  UNIQUE(question_id, rule_id)
```

This makes it possible to: display the rule behind an answer; find **every** question
affected when a rule changes (query `QuestionRule` by `rule_id`); flag those questions for
re-review after legislation changes; and store provenance. Optional free-form
`Question.source_refs` (json) may still hold extra non-legal references, but legal
provenance is the structured `Rule`/`QuestionRule` link.

## Media (metadata in DB, bytes in object storage)

```
QuestionMedia
  id
  media_type          MediaType      (image | video | gif)
  content_type        str            (image/webp | video/mp4 | video/webm | image/gif)
  content_hash        str            # sha256 of the stored bytes; used in the URL
  storage_key         str            # object-storage key/path
  poster_hash         str?           # content hash of the video poster still (if video)
  alt_text_uz         text?          # language-specific only if the image bakes in text
  width / height      int?
  duration_ms         int?           (video/gif)
  byte_size           int
```

- Bytes live in **S3-compatible object storage** (R2/S3/MinIO). Postgres stores only
  metadata + `content_hash` + `storage_key`.
- Serving URL is **content-addressed**: `/api/question-media/{media_id}/{content_hash}`
  (or a direct/signed object-storage URL). Because the hash changes when an admin replaces
  media, the URL changes too, so **long immutable caching is safe** and stale media is
  impossible. See [05-architecture.md](05-architecture.md) for the DB-media MVP fallback and
  its explicit size threshold.
- Media is **language-neutral** and shared across translations, except images with baked-in
  text (avoid where possible).

## Practice (repeatable attempts)

```
PracticeSession
  id
  user_id             (index)
  category            Category
  topic               Topic?         # null => mixed
  source              enum(topic, mixed, mistakes, sign_trainer)
  started_at / ended_at?

PracticeAnswer
  id
  practice_session_id (index)
  question_id
  selected_option_id?
  is_correct          bool
  time_spent_seconds  int?
  attempted_at
```

There is **no** global `(user, question)` uniqueness. A user may answer the same question
again in a later session — this is required for **mistakes review** and normal re-practice.
`PracticeAnswer` is intentionally distinct from `MockAnswer`.

## Mock exam (self-contained snapshot)

```
MockAttempt
  id
  user_id             (index)
  category            Category
  language            Language                 # snapshot of the user's language at start
  status              MockStatus
  started_at
  expires_at                                   # = started_at + time_limit_seconds (authoritative)
  completed_at?
  # snapshot of the applicable exam config (from the single source of truth):
  exam_config_version int
  question_count      int                      # snapshot (20)
  time_limit_seconds  int                      # snapshot (1500)
  pass_correct        int                      # snapshot (18)
  # results (set on submit/expiry):
  correct_count       int?
  answered_count      int?
  passed              bool?                     # correct_count >= pass_correct
  result_json         json?                     # per-topic breakdown, mistakes, avg answer time

MockQuestion
  id
  mock_attempt_id     (index)
  question_id
  position            int
  UNIQUE(mock_attempt_id, question_id)          # unique, without replacement
  UNIQUE(mock_attempt_id, position)             # stable order

MockAnswer
  id
  mock_attempt_id     (index)
  question_id
  selected_option_id?
  is_correct          bool?                      # graded at submit
  marked_for_review   bool = false
  answered_at?
  UNIQUE(mock_attempt_id, question_id)
```

Start-of-mock behaviour (see [03-features.md](03-features.md) for the flow):
- select **20 random, unique, published** questions where `category` = user's category and a
  `uz` translation exists; **without replacement**; persist them as `MockQuestion` rows with
  positions;
- set `started_at` and `expires_at = started_at + time_limit_seconds`;
- snapshot the exam-config values;
- reopening/refreshing returns the **same** snapshot — it never regenerates the set or the
  deadline.

Result semantics: **pass/fail** (`passed`), not a 400–1600 score. `result_json` records the
missed questions with their topics and the average answer time for the review screen.

## Mistakes

```
MistakeEntry
  id
  user_id             (index)
  question_id
  first_missed_at
  last_missed_at
  miss_count          int
  resolved            bool                       # true once re-answered correctly (v1)
  last_result         bool
  UNIQUE(user_id, question_id)
```

A wrong answer in practice **or** mock creates/updates the entry. v1 resolves an entry on
the first correct re-answer; spaced-repetition scheduling is v2.

## Readiness (computed; optional snapshot)

The algorithm, components, thresholds, and "not enough data" behaviour are fully specified
in [07-readiness.md](07-readiness.md). Thresholds/weights live in domain configuration
(alongside the exam config), not env vars.

```
ReadinessSnapshot   (optional cache)
  id
  user_id
  category
  score               int?               # null when "not enough data"
  label               enum(insufficient_data, initial, ready_estimate)
  exam_ready          bool
  components_json     json                # the four component scores + confidence inputs
  computed_at
```

## Reused as-is from SATStudy

`User`; `StudentProfile` (keep display_name, category, target_exam_date, daily_goal,
timezone, language, onboarding_completed; drop SAT score fields); `Streak`,
`StudentDailyStat`, `StudentWeeklyStat` (daily goals/streaks kept — cheap to reuse);
`AdminAuditEvent`. Leaderboard/scoreboard tables and `NotificationEvent` are **deferred**
(see [03-features.md](03-features.md#scope--priorities)).
