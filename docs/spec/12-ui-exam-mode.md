# 12 — UI: exam mode

A dedicated **ExamMode** UI, visually distinct from practice, that mirrors the real
Uzbekistan theory terminal **as closely as verified behavior allows** — no more, no less.

## Verified vs. observed vs. unknown

We state only what is verified. Design may **approximate** an observed layout, but we must not
claim our UI is an "exact copy of the official exam."

**Verified** (from [`research/uzbekistan-driving-license.md`](../../research/uzbekistan-driving-license.md)):
- 20 questions; single **continuous 25-minute** timer; 2–5 options; exactly one correct;
  automatic end at expiry; questions may be **static or animated**; result + right/wrong +
  time shown after completion; **no** aids during the exam.

**Observed from credible exam-centre material** (needs confirmation before we rely on visuals):
- terminal-style, plain single-question screen with a question navigator/grid. **UNVERIFIED**
  in this pass (no live web access) — treat as a research target.

**Unknown (research required, do not lock):**
- exact terminal layout/branding, colors, fonts;
- whether animations can be **replayed** and how many times;
- whether navigation allows free jumping vs. forward-only;
- on-screen labels/wording.

> Research task before finalizing visuals: gather legitimate photos/videos/news/exam-centre
> walkthroughs/screenshots of actual terminals; record findings under Verified / Observed /
> Unknown and cite sources. Use them as **design research only** unless reuse rights are
> explicit.

## Entering exam mode

When a mock starts, the app **explicitly enters an exam-focused mode** that is visually and
behaviorally different from practice. It suppresses all non-exam UI: **no** streak animations,
points, celebratory UI, learning tips, gamification, or distracting navigation. A short
confirmation precedes entry ("Imtihon rejimi boshlanadi — 20 savol, 25 daqiqa").

## Layout (approximation — plain, focused, test-like)

```
┌─────────────────────────────────────────┐
│ Savol 7 / 20                    17:43    │   ← index + single global timer
├─────────────────────────────────────────┤
│                                          │
│              IMAGE / VIDEO               │   ← media (if any)
│                                          │
├─────────────────────────────────────────┤
│ Savol matni                              │
│                                          │
│ ○ A. ...                                 │
│ ○ B. ...                                 │
│ ○ C. ...                                 │
│ ○ D. ...                    (2–5 options)│
│                                          │
├─────────────────────────────────────────┤
│ 1 2 3 4 5 6 [7] 8 … 20                    │   ← navigator (answered/marked/current states)
│                       Keyingi →          │
└─────────────────────────────────────────┘
```

- Timer is display-only; the deadline is server-side `expires_at`
  ([05-architecture.md](05-architecture.md)).
- The navigator shows answered / marked-for-review / current; **mark for review** is allowed.
- **No answer/explanation/rule is shown** while the attempt is `in_progress` — the API does
  not even send correctness ([09-security.md](09-security.md#exam-integrity-critical)).
- **Mobile Telegram**: the layout adapts to narrow width (media on top, options stacked,
  navigator collapsible) **without changing exam behavior or timing**.

## Media in exam mode

- Images/GIFs render inline; **video** autoplays **muted, `playsinline`**.
- **Animation replay**: allow a minimal **replay** control **only if** research confirms the
  real exam permits re-viewing the animation; otherwise match verified behavior. Until
  confirmed, default to **allowing replay** of our own looping clips (looping is the natural
  MP4/WebM behavior) but keep controls minimal — and revisit once exam behavior is verified.
- **No information leakage via poster/thumbnail**: the poster still must **not** reveal
  information the animation withholds at its start (e.g. don't use a last-frame poster that
  gives away the outcome). Use the **first frame** as the poster.
- Keep playback controls minimal (no scrubbing timeline that could imply answer timing).

## Result & review (after completion)

On submit or auto-submit at expiry, leave exam mode and show the result
([03-features.md](03-features.md#submission-and-result)): `NN/20`, pass/fail, missed list with
topics, average answer time; then a full **review** that reveals correct answers, per-option
explanations, and rules — rendered from the **pinned `question_version_id`** so the review
matches exactly what was taken.

## Claims discipline

Copy may say the mock "follows the real exam format (20 questions, 25 minutes, 18/20 to pass)"
— all verified. Copy must **not** claim it is the official exam or an exact replica of the
terminal UI unless/until that is verified with cited sources.
