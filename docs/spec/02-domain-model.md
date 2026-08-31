# 02 — Domain model

Adapted from the SATStudy SQLAlchemy models. Names below are logical; final table names
follow the existing `snake_case` convention. Every entity keeps `id` (UUID string),
`created_at`, `updated_at` unless noted.

## Mapping from SATStudy

| SATStudy | prava-bot | Change |
| --- | --- | --- |
| `Section` enum (math/reading_writing) | `Category` enum (`B`, later `A`,`A1`,`C`,`D`) | replace |
| `Question.topic` / `.skill` (free text) | `Topic` (controlled) + `subtopic` + `rule_refs` | tighten |
| `QuestionImage` (image only) | `QuestionMedia` (image / video / gif) | extend |
| `AnswerOption` (A–D, one correct) | `AnswerOption` (2–5, one correct) | relax count |
| SPR (`student_produced_response`) | **removed** | drop |
| `ExamTemplate` adaptive 4-module | `MockTemplate` single 20-question set | simplify |
| `ExamAttempt` + adaptive routing | `MockAttempt` single module + pass/fail | simplify |
| 400–1600 score fields | pass/fail + correct count | replace |
| — | `MistakeEntry` | add |
| — | `ReadinessSnapshot` (or computed) | add |

## Enums

- `Category`: `B` (v1). Reserved: `A`, `A1`, `C`, `D`.
- `Topic`: the 15 YHQ groups from [06-content-plan.md](06-content-plan.md), e.g.
  `general_rules`, `road_signs`, `road_markings`, `signals`, `intersections`,
  `manoeuvring`, `speed_distance`, `overtaking`, `stopping_parking`, `vulnerable_users`,
  `railway_crossings`, `motorways_special`, `vehicle_condition`, `transport_of_people_cargo`,
  `emergencies_first_aid`.
- `QuestionStatus`: `draft`, `reviewed`, `published`, `archived` (unchanged).
- `MediaType`: `image`, `video`, `gif`.
- `MockStatus`: `in_progress`, `completed`, `abandoned`.

## Question

```
Question
  id
  category            Category      (index)
  topic               Topic         (index)
  subtopic            str?          (free text within topic)
  status              QuestionStatus (index)
  language            str           = "uz"   (see 04-i18n.md)
  prompt              text          (the question text; may be empty if media is self-contained)
  options             [AnswerOption] (2–5)
  media               QuestionMedia? (0 or 1)
  short_explanation   text?         (shown in practice + review)
  rule_refs           json[str]     (e.g. ["YHQ:13.9"]) — the rule(s) the question teaches
  source_refs         json[str]?    (provenance / verification links)
  difficulty          int           (1–3; drives mock variety, not the exam)
  content_version     int           = 1
  verified_at         date?
  created_by_user_id / updated_by_user_id
```

Publish validation (backend): non-empty prompt **or** media present; **2–5** options;
**exactly one** `is_correct`; every option has an explanation; at least one `rule_ref`.

## AnswerOption

```
AnswerOption
  id
  question_id     (index)
  label           str   ("A".."E")
  text            text
  position        int   (1..5)
  is_correct      bool
  explanation     text  (why right/wrong — shown after answering in practice/review)
```

Constraint: 2 ≤ options ≤ 5; exactly one `is_correct` when the question is published.

## QuestionMedia

Replaces SATStudy's image-only model. One media item per question (v1).

```
QuestionMedia
  id
  question_id     (unique, index)
  media_type      MediaType         (image | video | gif)
  content_type    str               (image/webp, video/mp4, video/webm, image/gif)
  data            bytes (deferred)   — stored in DB like SATStudy images (see 05-architecture.md)
  poster          bytes? (deferred)  — still frame for video (first-frame thumbnail)
  alt_text        text?
  duration_ms     int?               (video/gif; for UI + validation)
  width / height  int?
  updated_at
```

Serving: `GET /api/questions/{id}/media` streams `data` with the right `content_type` and
long immutable cache; drafts are admin-only (mirrors SATStudy image auth). Video is served
with `Accept-Ranges` where practical. See [05-architecture.md](05-architecture.md) for the
upload pipeline, size limits, and CSP `media-src`.

## Practice

```
PracticeSession       (user_id, category, topic?, source, started_at, ended_at?)
QuestionAttempt
  id
  user_id             (index)
  question_id
  practice_session_id?
  selected_option_id?
  is_correct          bool
  time_spent_seconds  int?
  attempted_at
  unique(user_id, question_id, mock_attempt_id?)   # see note
```

Note: SATStudy enforces one attempt per (user, question) globally so practice never repeats
a question. For prava-bot we want **repeat practice** (especially mistakes review), so the
uniqueness is scoped per session/mock rather than globally. Exact constraint decided in
implementation, but the requirement is: a user can re-answer a question in a later session.

## MistakeEntry

```
MistakeEntry
  id
  user_id             (index)
  question_id
  first_missed_at
  last_missed_at
  miss_count          int
  resolved            bool          (set true once answered correctly enough times)
  last_result         bool
```

Drives the **Mistakes review** feature. (Spaced-repetition scheduling is v2; v1 just
queues unresolved mistakes, hardest/most-recent first.)

## Mock exam

```
MockTemplate
  id
  name
  category            Category
  status              (draft | published | archived)
  question_count      int   = 20
  time_limit_seconds  int   = 1500
  pass_correct        int   = 18       # per-category, from exam constants
  selection           enum  (random_from_bank | fixed_set)
  # fixed_set uses MockTemplateQuestion rows; random_from_bank samples at start time

MockTemplateQuestion (template_id, question_id, position)   # only for fixed_set

MockAttempt
  id
  user_id             (index)
  mock_template_id?
  category
  status              MockStatus
  started_at / completed_at
  time_limit_seconds
  remaining_seconds
  correct_count       int?
  answered_count      int?
  passed              bool?           # correct_count >= pass_correct
  result_json         json?           # per-topic breakdown, mistakes list, avg time

MockAnswer
  id
  mock_attempt_id     (index)
  question_id
  position
  selected_option_id?
  is_correct          bool?
  marked_for_review   bool
```

Result semantics: **pass/fail** (`passed`), not a 400–1600 score. `result_json` records the
mistakes with their topics and average answer time for the review screen.

## Readiness

Readiness may be computed on read or snapshotted. Model (from research §16):

```
readiness = 0.40 * recent_mock_performance
          + 0.30 * topic_mastery
          + 0.20 * mistake_recovery
          + 0.10 * consistency_recency
```

"Exam-ready" gate (advisory, shown to user):
- ≥ 3 recent mock exams, **and**
- ≥ 2 of the last 3 at ≥18/20, **and**
- no major topic below 70%, **and**
- enough unique questions attempted to avoid memorising a small sample.

```
ReadinessSnapshot? (optional cache)
  user_id, category, score, computed_at, components_json
```

## Reused as-is from SATStudy

`User`, `StudentProfile` (drop SAT-specific score fields; keep display_name, category,
target_exam_date, daily_goal, timezone, onboarding_completed), `Streak`,
`StudentDailyStat`, `StudentWeeklyStat`, `AdminAuditEvent`, `NotificationEvent` (v2).
Leaderboards reuse the daily/weekly stat + scoreboard logic unchanged.
