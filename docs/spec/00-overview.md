# 00 — Overview

## Vision

Help people in Uzbekistan pass the **driving-license theory exam (YHQ)** on the first
attempt by practising in an environment that mirrors the real exam and that teaches the
rule behind every answer.

Since **February 2026**, category A/B candidates may study theory independently (no
mandatory auto-school theory course — see [01-exam-and-rules.md](01-exam-and-rules.md)).
That reform makes an independent-study product genuinely useful rather than merely
supplementary.

## Product shape

A single platform with two surfaces, reusing the SATStudy pattern:

- **React mini web app** opened as a **Telegram Web App** — the place users study, take
  mock exams, and view progress. Best for image- and animation-heavy questions and timed
  exams.
- **Telegram bot** — launches the mini app and (v2) sends retention nudges.

Exam scoring and answer correctness are **deterministic backend logic**. An LLM is never
asked whether an answer is correct. (LLM use, if any, is limited to drafting or rephrasing
explanations that are then reviewed before publishing.)

## v1 scope (MVP)

1. **Onboarding** — minimal: display name, category (default B), optional target exam date,
   timezone. No long form before the first question.
2. **Practice by topic** — pick a YHQ topic, answer questions one at a time, get
   **immediate explanations** (per-option + rule reference).
3. **Mistakes review** — every wrong answer enters a mistakes queue the user can re-practise.
4. **Mock exam simulation** — full real-exam fidelity: 20 questions, one 25-minute timer,
   2–5 options, one correct, **pass at ≥18/20**, photos and animations, no mid-exam hints,
   result + review afterward.
5. **Progress / readiness dashboard** — readiness score, recent mock results, weak topics,
   daily goal, streak.
6. **Streaks, daily goals, leaderboards** — carried over from SATStudy.
7. **Admin studio** — author/publish questions with image/animation upload, tag topic +
   rule reference, write per-option explanations, and build mock templates.

All v1 UI and content are in **Uzbek (Latin script)**.

## Non-goals (v1)

- Not a practical-driving simulator. The practical exam (autodrome + city, penalty-point
  scoring) is **out of scope** for v1; the research flags that its rules need separate
  verification per exam centre.
- Not a legal/administrative service (no application filing, no medical-certificate issuance).
- No Russian/Cyrillic, no categories other than B, no sign/situation trainers, no
  spaced-repetition, no exam-day checklist — these are **v2** (see
  [README.md](README.md#deferred-to-v2)).
- Never claim an internally authored question is an "official exam question."

## Success metrics

- Diagnostic → first-practice conversion.
- Questions answered per active day; 7-day return rate.
- Share of users who complete at least one mock exam.
- Average mock-score improvement over time.
- Mistake-recovery rate (wrong questions later answered correctly).
- Share of users reaching the readiness threshold.
- North-star (self-reported): **% of prepared users who pass the official theory exam on
  the first attempt.**

## Content ambition for v1 launch

- All ~15 topic groups represented (see [06-content-plan.md](06-content-plan.md)).
- Enough verified original questions per topic that repeated mock exams do not become a
  memorisation exercise (target 30–50 per major topic where appropriate).
- Explanations and rule references are reliable **before** raw question count is optimised.
