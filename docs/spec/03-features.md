# 03 — Features

## Scope & priorities

v1 feature priority order:

1. **Practice** (by topic / mixed)
2. **Explanations** (per-option + rule, after answering)
3. **Mistakes** review
4. **Road signs** trainer
5. **Mock exams** (full real-exam fidelity)
6. **Readiness / progress**

**Daily goals and streaks** are kept because they are cheap to reuse from SATStudy.
**Leaderboards are deferred** (no strong v1 product reason; they add ranking/scoreboard
surface and social pressure that is not core to passing the theory test). Deferred to v2:
situation trainer, spaced-repetition scheduling, exam-day checklist, Russian/Cyrillic,
additional categories, Telegram reminder messages.

## Onboarding

Minimal, single screen (no long form before the first question):
- display name;
- category (default **B**, only option in v1);
- language (**uz** only in v1; the field exists for v2);
- optional target exam date;
- timezone (auto-detected, editable).

Then optionally offer a short **10-question diagnostic** that seeds the initial readiness
estimate and weak-topic list. The diagnostic is skippable.

## Practice by topic (with explanations)

The core learning loop.

1. User picks a **topic** (or "mixed").
2. One question at a time: prompt + media (image / looping muted video / GIF) + 2–5 options.
3. User selects an option and submits.
4. **Immediate feedback**: correct/incorrect banner; the correct option highlighted;
   **per-option explanation**; the **rule** behind the answer (`Rule.text_uz` via
   `QuestionRule`) and the question's `short_explanation`.
5. "Continue" loads the next question (a fresh `PracticeAnswer` — questions may recur across
   sessions).

Requirements:
- Media renders inline; video **autoplays muted, loops, `playsinline`**, with a poster
  frame fallback and a manual replay control; respects reduced-motion.
- Explanations appear **only after** the user answers.
- Wrong answers create/update a `MistakeEntry`.

## Mistakes review

- A queue of the user's unresolved mistakes (`MistakeEntry.resolved = false`), ordered
  hardest/most-recent first (`miss_count` desc, `last_missed_at` desc).
- Same answer + explanation flow as practice (runs as a `PracticeSession` with
  `source = mistakes`).
- v1 resolves an entry on the first correct re-answer.

## Road-sign trainer (v1)

A fast visual drill over sign questions, reusing the same question/rule infrastructure.

- Pool: published questions with `is_sign_question = true` (topic `road_signs`).
- Flow: **show sign → choose meaning → submit → immediate correction + explanation + rule →
  next sign.**
- Card-style, quick pace; wrong answers feed the same `MistakeEntry` queue.
- No separate content pipeline — signs are ordinary `Question` records flagged for this mode.

(The advanced **situation trainer** for intersections/manoeuvres remains v2.)

## Mock exam simulation (maximum real-exam fidelity)

Mirrors the official theory exam ([01-exam-and-rules.md](01-exam-and-rules.md)). There are
**no mock templates** and **no separate exam bank** — questions come from the shared bank.

### Start

- Our app selects **20 random, unique, published** questions for the user's category (B) and
  language (`uz`), **without replacement**, and snapshots them as `MockQuestion` rows with
  fixed positions.
- Set `started_at` and `expires_at = started_at + 1500s`; snapshot the exam-config values
  onto the `MockAttempt`.
- **No topic quota / blueprint** — selection is uniform random from the eligible bank.
- Copy must say *our app* selects from *our* bank; it must **not** claim the official exam
  uses our bank or a specific algorithm (see [01-exam-and-rules.md](01-exam-and-rules.md)).

### During the exam

- 20 questions, **2–5 options**, exactly one correct; media shown like the real exam.
- **Continuous global 25-minute timer.** The deadline is `expires_at`, computed and enforced
  **server-side**:
  - closing Telegram/the browser does **not** stop the timer;
  - reopening computes remaining time as `expires_at - now` (never from client state);
  - the client can **never** extend the deadline;
  - **there is no pause/resume.**
- **No hints, no explanations, no correct-answer reveal** during the exam.
- Question navigator: jump between questions, **mark for review**, see answered/unanswered.

### Network-loss behaviour

- Answers may be **buffered locally** while offline.
- On reconnect, the client **syncs pending answers** to the server.
- The server's `expires_at` remains **authoritative**; **offline time still counts** against
  the 25 minutes. A sync that arrives after `expires_at` does not change the outcome for
  those questions.

### Submission and result

- On explicit submit **or** when `now >= expires_at`, the server grades: `correct_count`,
  `answered_count`, `passed = correct_count >= pass_correct` (18).
- Auto-submit at expiry happens server-side even if the client is gone; the next time the
  attempt is loaded it is already `completed`.

Result screen:

```
18 / 20 — O'TDINGIZ (PASS)      |      15 / 20 — YIQILDINGIZ (FAIL)
Vaqt: 17:42

Xatolar:
- 7-savol · Chorrahalar
- 14-savol · To'xtash va to'xtab turish

O'rtacha javob vaqti: 53 s
```

Post-exam **review**: full per-question review with the correct answer, per-option
explanations, and the rule (now revealed). Missed questions feed the mistakes queue.

## Progress / readiness dashboard

Home screen (research §14), driven by [07-readiness.md](07-readiness.md):
- **readiness** — a percentage **only when enough data exists**; otherwise
  `Ma'lumot yetarli emas` ("not enough data") or an `Initial level: NN%` label;
- recent mock result(s);
- **weak topics** (lowest topic mastery);
- today's daily-goal progress and streak;
- primary actions: **Continue practice** and **Start mock exam (20 / 25 min)**.

The advisory **"exam ready"** badge appears only when the readiness gate is met (≥3 recent
mocks; ≥2 of last 3 at ≥18/20; no major topic below 70%; enough unique questions attempted).
Thresholds are domain configuration.

## Admin studio

Reuse SATStudy's admin question studio, adjusted for driving content. **Mock-template
building is removed** (mocks are generated from the shared bank at start time).

- create/edit/publish/archive questions; draft→reviewed→published lifecycle;
- author text as **translations** (`uz` in v1): prompt, `short_explanation`, and each
  option's text + explanation;
- **media upload** (image / MP4 / WebM / GIF) → object storage; content-hash + poster
  generation; alt text (see [05-architecture.md](05-architecture.md));
- set **category**, **topic**, **subtopic**, **difficulty**, and `is_sign_question`;
- edit **2–5 options**, mark the one correct;
- link one or more **`Rule`** records (required to publish) + manage the `Rule` catalog;
- publish validation enforces the rules in
  [02-domain-model.md](02-domain-model.md#question-and-content-translation-ready);
- admin overview + practice analytics (weak topics, most-missed) reused from SATStudy;
- when a `Rule` changes, the studio can list all questions linked to it for re-review;
- all admin actions gated by `ADMIN_TELEGRAM_IDS`; dev login gated to
  `APP_ENV=development` (see [05-architecture.md](05-architecture.md#security)).

## Deferred to v2 (not built now)

Leaderboards; situation trainer; spaced-repetition; exam-day checklist; Russian + Cyrillic;
additional categories (A/A1/C/D); Telegram retention/reminder messages.
