# 00 — Overview

## Vision

Help people in Uzbekistan pass the **driving-license theory exam (YHQ)** on the first
attempt by practising in an environment that mirrors the real exam and that teaches the rule
behind every answer.

Since **February 2026**, category A/B candidates may study theory independently (no mandatory
auto-school theory course — see [01-exam-and-rules.md](01-exam-and-rules.md)). That reform
makes an independent-study product genuinely useful.

## Product shape

A single platform, reusing the SATStudy pattern:

- **React mini web app** opened as a **Telegram Web App** — where users study, take mock
  exams, and view progress. Best for image/animation-heavy questions and timed exams.
- **Telegram bot** — launches the mini app (retention nudges are v2).

Exam scoring and answer correctness are **deterministic backend logic**. An LLM is never
asked whether an answer is correct; LLM use, if any, is limited to drafting/rephrasing
explanations that are reviewed before publishing.

## v1 scope (MVP)

Priority order: **practice → explanations → mistakes → road signs → mock exams →
readiness/progress.**

1. **Onboarding** — minimal (display name, category B, language uz, optional exam date,
   timezone). No long form before the first question.
2. **Practice by topic** — one question at a time with **immediate explanations** (per-option
   + the linked YHQ rule).
3. **Mistakes review** — every wrong answer queues for re-practice.
4. **Road-sign trainer** — fast visual drill over sign questions (same question/rule
   infrastructure).
5. **Mock exam simulation** — full real-exam fidelity: 20 questions from the **shared bank**,
   one **continuous 25-minute** timer, 2–5 options, one correct, **pass at ≥18/20**, photos
   and animations, no mid-exam hints, result + review afterwards.
6. **Readiness / progress dashboard** — a data-gated readiness score (see
   [07-readiness.md](07-readiness.md)), recent mock results, weak topics, daily goal, streak.
7. **Admin studio** — author/publish questions (translations), upload image/animation media,
   set topic + link YHQ **rules**, write per-option explanations. **No mock-template
   building** — mocks are generated from the shared bank.

**Daily goals and streaks** are kept (cheap to reuse). All v1 UI and content are **Uzbek
(Latin)**.

## Non-goals (v1)

- Not a practical-driving simulator (autodrome/penalty scoring is out of scope; its rules
  need separate per-centre verification).
- Not a legal/administrative service (no application filing, no medical-certificate issuance).
- **Deferred to v2**: leaderboards; situation trainer; spaced-repetition; exam-day checklist;
  Russian/Cyrillic; categories other than B; Telegram reminder messages.
- Never claim an internally authored question is an "official exam question."
- No fixed/claimed per-topic exam distribution.

## Locked v1 principles (do not weaken)

- category B only; Uzbek Latin only;
- 20 questions; **continuous** 25-minute global timer; 18/20 to pass;
- 2–5 options; exactly one correct;
- no hints/explanations during the mock; explanations after practice answers and after mock
  completion;
- every publishable question has **verified rule provenance** (`Rule`/`QuestionRule`);
- one **shared** question bank for practice and mocks (no separate exam bank, no templates);
- theory facts stay synchronized with
  [`research/uzbekistan-driving-license.md`](../../research/uzbekistan-driving-license.md).

## Success metrics

- Diagnostic → first-practice conversion; questions/active day; 7-day return rate.
- Share of users completing a mock; average mock-score improvement; mistake-recovery rate.
- Share reaching the readiness threshold.
- North-star (self-reported): **% of prepared users who pass the official theory exam on the
  first attempt.**

## Content ambition for v1 launch

- All 15 topic groups represented (see [06-content-plan.md](06-content-plan.md)).
- Enough verified original questions per topic that repeated mocks are not memorisation
  (target 30–50 per major topic; a few hundred published questions before promoting mocks
  heavily).
- Reliable explanations and rule links **before** optimising raw question count.
