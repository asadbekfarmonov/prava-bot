# 03 — Features

## Onboarding

Minimal, single screen (no long form before the first question):
- display name;
- category (default **B**, only option in v1);
- optional target exam date;
- timezone (auto-detected, editable).

After saving, optionally offer a short **10-question diagnostic** that seeds the initial
readiness estimate and weak-topic list. Diagnostic is skippable.

## Practice by topic (with explanations)

The core learning loop.

1. User picks a **topic** (or "mixed").
2. One question at a time: prompt + media (image / looping muted video / GIF) + 2–5 options.
3. User selects an option and submits.
4. **Immediate feedback**:
   - correct/incorrect banner;
   - the correct option highlighted;
   - **per-option explanation** (why each is right/wrong);
   - **rule reference** (`rule_refs`) and the `short_explanation`.
5. "Continue" loads the next question.

Requirements:
- Media renders inline; video **autoplays muted, loops, `playsinline`**, with a poster
  frame fallback and a manual replay control.
- Explanations are shown **only after** the user answers (never before).
- Wrong answers create/update a `MistakeEntry`.

## Mistakes review

- A dedicated queue of the user's unresolved mistakes (`MistakeEntry.resolved = false`).
- Ordered hardest/most-recent first (miss_count desc, last_missed_at desc).
- Same answer + explanation flow as practice.
- Answering correctly progresses the entry toward `resolved` (v1: resolve on first correct
  re-answer; spaced-repetition tuning is v2).

## Mock exam simulation (maximum real-exam fidelity)

Mirrors the official theory exam ([01-exam-and-rules.md](01-exam-and-rules.md)):

- **20 questions**, drawn per the template (`random_from_bank` default, or a `fixed_set`).
- **One global 25-minute countdown** (1500 s). Timer visible; auto-submits at 0.
- **2–5 options**, exactly one correct; media shown just like the real exam.
- **No hints, no explanations, no correct-answer reveal** during the exam.
- Question navigator: jump between questions, **mark for review**, see answered/unanswered.
- Answers autosave; the attempt can be paused/resumed with remaining time preserved
  (reuse SATStudy's pause/beacon mechanism).
- On submit or timeout → compute `correct_count`, `passed = correct_count >= 18`.

### Result screen

```
18 / 20 — O'TDINGIZ            (PASS)   |   xato: 2 — YIQILDINGIZ (FAIL)
Vaqt: 17:42

Xatolar:
- 7-savol · Chorrahalar
- 14-savol · To'xtash va to'xtab turish

O'rtacha javob vaqti: 53 s
Imtihonga tayyorlik: 81%

[ Xatolarni ko'rib chiqish ]
```

Post-exam **review**: full per-question review with the correct answer, per-option
explanations, and rule references (now revealed, since the exam is over). Missed questions
feed the mistakes queue.

## Progress / readiness dashboard

Home screen shows, at a glance (research §14):
- **readiness score** (0–100%) with the component breakdown available on tap;
- recent mock result(s);
- **weak topics** (lowest topic mastery);
- today's daily-goal progress and streak;
- primary actions: **Continue practice** and **Start mock exam (20 / 25 min)**.

The "exam-ready" advisory badge uses the gate in
[02-domain-model.md](02-domain-model.md#readiness).

## Streaks, daily goals, leaderboards

Carried over from SATStudy unchanged in behaviour:
- daily goal (configurable count) and streak with the same expiry logic;
- daily and weekly leaderboards (points, accuracy) including all users;
- points model reused (correct > incorrect).

## Admin studio

Reuse SATStudy's admin question studio, extended for driving content:
- create/edit/publish/archive questions; draft→reviewed→published lifecycle;
- **media upload** supporting image, MP4/WebM, and GIF (see
  [05-architecture.md](05-architecture.md)); alt text; auto poster frame for video;
- set **category**, **topic**, **subtopic**, **difficulty**;
- edit **2–5 options**, mark the one correct, write each option's explanation;
- set `rule_refs` (required) and optional `source_refs`;
- publish validation enforces the rules in [02-domain-model.md](02-domain-model.md#question);
- build **mock templates** (`random_from_bank` or `fixed_set`), publish/archive;
- admin overview + practice analytics (weak topics, most-missed) reused from SATStudy;
- all admin actions gated by `ADMIN_TELEGRAM_IDS`; dev login gated to
  `APP_ENV=development` (see [05-architecture.md](05-architecture.md#security)).

## Deferred to v2 (not built now)

- Road-sign **card trainer** (fast swipe/flashcards).
- **Situation trainer** (dedicated intersection/manoeuvre diagram drills).
- **Spaced-repetition** scheduling for mistakes.
- **Exam-day checklist** (medical cert, application, retake windows, issuance).
- **Russian + Cyrillic**; additional categories (A/A1/C/D).
- Telegram retention nudges / daily reminder messages.
