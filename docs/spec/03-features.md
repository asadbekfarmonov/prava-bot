# 03 — Features

## Scope & priorities

v1 priority order:

1. **Practice** (by topic / mixed)
2. **Explanations** (per-option + rule, after answering)
3. **Mistakes** review
4. **Road signs** trainer
5. **Mock exams** (full real-exam fidelity)
6. **Readiness / progress**
7. **Rankings** (competitive but learning-weighted)

**Daily goals and streaks** are kept (cheap; also feed ranking consistency). **Rankings are a
v1 feature** ([10-ranking.md](10-ranking.md)). Deferred to v2: situation trainer,
spaced-repetition, exam-day checklist, Russian/Cyrillic, additional categories, Telegram
reminder messages.

## Onboarding

Minimal, single screen: display name; category (B, only option in v1); language (uz only in
v1); optional target exam date; timezone. Then an optional, skippable **10-question
diagnostic**.

### Diagnostic output (NOT readiness)

The diagnostic never shows an exam-readiness percentage. It shows a raw score and topic
guidance, and seeds the weak-topics list ([07-readiness.md](07-readiness.md#diagnostic-is-not-readiness)):

```
Boshlang'ich natija: 7/10

Kuchli mavzular: Yo'l belgilari, To'xtash va to'xtab turish
Mashq qilish kerak: Chorrahalar, Quvib o'tish
```

`Imtihonga tayyorlik` (readiness %) only appears once the readiness `ready_estimate` state is
reached.

## Practice by topic (with explanations)

1. Pick a **topic** (or "mixed").
2. One question at a time: prompt + media (image / looping muted video / GIF) + 2–5 options.
3. Select an option and submit.
4. **Immediate feedback** meeting the **explanation-quality standard**
   ([06-content-plan.md](06-content-plan.md#explanation-quality-standard)): your answer vs.
   correct; **why the correct option**; **why each wrong option is wrong**; the **rule**
   (`Rule`/`RuleTranslation` via `QuestionVersionRule`); and a short "Eslab qoling".
5. Continue → next question (a new `PracticeAnswer`; questions may recur across sessions).

Media autoplays muted, loops, `playsinline`, poster fallback, reduced-motion respected.
Explanations appear **only after** answering. Wrong answers upsert a `MistakeEntry`.

## Mistakes review

Queue of unresolved mistakes (hardest/most-recent first), same explanation flow, run as a
`PracticeSession` with `source = mistakes`. v1 resolves on first correct re-answer; correct
resolution can award ranking points ([10-ranking.md](10-ranking.md)).

## Road-sign trainer (v1)

Fast visual drill over `is_sign_question` questions: **show sign → choose meaning → submit →
immediate correction + explanation + rule → next**. Reuses the same question/rule
infrastructure; wrong answers feed the mistakes queue. (Advanced **situation trainer** is v2.)

## Mock exam simulation (maximum real-exam fidelity)

No templates, no separate bank — questions come from the shared bank. Full UI/behavior in
[12-ui-exam-mode.md](12-ui-exam-mode.md); integrity controls in
[09-security.md](09-security.md#exam-integrity-critical).

### Start
- Select **20 random, unique, published** questions for the user's category (B) + language
  (uz), **without replacement**; **pin each question's current immutable `question_version_id`**
  into `MockQuestion` so later edits never alter this attempt.
- Set `started_at` + `expires_at = started_at + 1500s`; snapshot the exam config.
- Uniform random selection — **no topic quota/blueprint**.
- Copy says *our app* selects from *our* bank; it must not claim the official exam uses our
  bank or a specific algorithm ([01-exam-and-rules.md](01-exam-and-rules.md)).

### During
- Enter a distinct **exam-focused mode** (no points/streaks/tips/gamification —
  [12-ui-exam-mode.md](12-ui-exam-mode.md)).
- 20 questions, 2–5 options, exactly one correct; media as in the real exam.
- **Continuous global 25-minute timer**, server-authoritative via `expires_at`: closing the
  app does not stop it; reopening computes remaining as `expires_at - now`; client can never
  extend it; **no pause/resume**.
- **No hints/explanations/correct-answer reveal**; the API does not even send correctness
  ([09-security.md](09-security.md#exam-integrity-critical)).
- Navigator with mark-for-review; answers autosave.

### Network loss
Answers may be buffered locally and synced on reconnect; server `expires_at` stays
authoritative; offline time still counts; a sync arriving after `expires_at` does not change
final results.

### Submission & result
On submit or when `now >= expires_at`, the server grades: `correct_count`, `answered_count`,
`passed = correct_count >= 18`. Auto-submit happens server-side even if the client is gone.

```
18 / 20 — O'TDINGIZ (PASS)      |      15 / 20 — YIQILDINGIZ (FAIL)
Vaqt: 17:42
Xatolar: 7-savol · Chorrahalar ; 14-savol · To'xtash va to'xtab turish
O'rtacha javob vaqti: 53 s
```

Post-exam **review** renders from the **pinned `question_version_id`** (exactly what was
taken) with correct answers, per-option explanations, and rules now revealed. Missed questions
feed the mistakes queue.

## Progress / readiness dashboard

Home screen ([07-readiness.md](07-readiness.md)): readiness state (a % only at
`ready_estimate`, else `Boshlang'ich daraja` or `Ma'lumot yetarli emas`, plus remaining topics
for coverage); recent mock result(s); weak topics; daily-goal + streak; ranking snapshot; and
primary actions **Continue practice** / **Start mock exam (20 / 25 min)**. The advisory "exam
ready" badge requires the full gate incl. **curriculum coverage**.

## Rankings (v1)

Learning-weighted, server-computed points with weekly/monthly/all-time boards, own-position
always shown, user-controlled display name, and opt-out — full model in
[10-ranking.md](10-ranking.md).

## Content reports

From any question (practice or mock review), a user can report an issue: **wrong answer,
unclear explanation, image problem, outdated rule, typo, other**. Reports capture the exact
`question_version_id` and land in the admin report queue
([08-admin.md](08-admin.md#content-reports-queue)).

## Admin studio

Full spec in [08-admin.md](08-admin.md): role-based dashboard, fast question editor with live
practice/mock/mobile preview, searchable Rule picker, review lifecycle, bulk import/ops,
duplicate detection, report queue, and pre-publish QA. **No mock-template building** (mocks are
generated from the shared bank). Editing a published question creates a **new immutable
version**.

## Deferred to v2

Situation trainer; spaced-repetition; exam-day checklist; Russian + Cyrillic; additional
categories (A/A1/C/D); Telegram reminder messages; region/city ranking.
