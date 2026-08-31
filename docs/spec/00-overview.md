# 00 — Overview

## Vision

Help people in Uzbekistan pass the **driving-license theory exam (YHQ)** on the first attempt
by practising in an environment that mirrors the real exam and that teaches the rule behind
every answer.

Since **February 2026**, category A/B candidates may study theory independently (no mandatory
auto-school theory course — [01-exam-and-rules.md](01-exam-and-rules.md)), which makes an
independent-study product genuinely useful.

## Product shape

A single platform: a **React mini web app** opened as a **Telegram Web App** (study, mocks,
progress), plus a **thin Telegram bot** that only sends `/start` → welcome + a button to open
the Mini App (retention nudges are v2). Exam scoring and answer correctness are **deterministic
backend logic**; an LLM is never asked whether an answer is correct (LLM use is limited to
drafting/rephrasing explanations that are human-reviewed —
[06-content-plan.md](06-content-plan.md#llm-assistance-policy)).

**Deployment**: **Railway** — one project with a single application service (FastAPI + aiogram
webhook + built Mini App + light jobs), Railway PostgreSQL, and a Railway S3-compatible Storage
Bucket for media. Production uses Telegram **webhooks**. Full design:
[13-deployment.md](13-deployment.md).

## v1 scope (MVP)

Priority: **practice → explanations → mistakes → road signs → mock exams → readiness/progress
→ rankings.**

1. **Onboarding** — minimal; optional skippable 10-question **diagnostic** (a raw score +
   topic guidance, **not** a readiness %).
2. **Practice by topic** — immediate feedback meeting the **explanation-quality standard**
   (per-option reasoning + linked YHQ rule + "remember this").
3. **Mistakes review** — every wrong answer queues for re-practice.
4. **Road-sign trainer** — fast visual drill over sign questions.
5. **Mock exam** — full real-exam fidelity: 20 questions from the **shared bank** (pinned to
   immutable versions), one **continuous 25-minute** server-authoritative timer, 2–5 options,
   one correct, **pass ≥18/20**, photos + animations, no mid-exam hints, a distinct exam-mode
   UI, then result + review.
6. **Readiness / progress** — a data-gated readiness score requiring **curriculum coverage**;
   never confident from a tiny sample.
7. **Rankings** — learning-weighted, server-computed points; weekly/monthly/all-time.
8. **Admin studio** — role-based authoring (author/reviewer/admin/superadmin) with fast
   editor + live preview, Rule picker, review lifecycle, bulk import/ops, duplicate detection,
   content-report queue, and pre-publish QA. **No mock-template building.**
9. **Content reports** — users flag issues; admins triage against the exact question version.

Daily goals/streaks are kept (cheap; feed ranking consistency). All v1 UI/content are **Uzbek
(Latin)**; the schema is translation-ready for Russian (v2).

## Non-goals (v1)

- Not a practical-driving simulator (out of scope; rules need per-centre verification).
- Not a legal/administrative service.
- **Deferred to v2**: situation trainer; spaced-repetition; exam-day checklist;
  Russian/Cyrillic; categories other than B; Telegram reminders; region/city ranking.
- Never claim internally authored content is an "official exam question," and never claim the
  mock UI is an exact copy of the official terminal unless verified.
- No fixed/claimed per-topic exam distribution.

## Locked v1 principles (do not weaken)

- category B only; Uzbek Latin only;
- 20 questions; **continuous** 25-minute global timer; 18/20 to pass; 2–5 options; exactly one
  correct;
- no hints/explanations during the mock; explanations after practice answers and after mock
  completion, meeting the explanation-quality standard;
- **immutable published question versions**; a mock/practice attempt is pinned to the exact
  version shown, so edits never alter historical attempts;
- one **shared** question bank (no separate exam bank, no templates);
- **correct answers never leak to the client during a live mock**;
- every publishable version has **verified rule provenance** and human verification;
- **rankings are server-computed** and reward learning, not question farming;
- theory facts stay synchronized with
  [`research/uzbekistan-driving-license.md`](../../research/uzbekistan-driving-license.md).

## Success metrics

Diagnostic→first-practice conversion; questions/active day; 7-day return; share completing a
mock; average mock-score improvement; mistake-recovery rate; share reaching the readiness
threshold. North-star (self-reported): **% of prepared users who pass the official theory exam
on the first attempt.**

## Content ambition for v1 launch

All 15 topics represented (required for readiness coverage); 30–50 verified original questions
per major topic; a few hundred published questions before promoting mocks heavily; reliable
explanations + rule links before optimising raw count ([06-content-plan.md](06-content-plan.md),
[11-content-acquisition.md](11-content-acquisition.md)).
