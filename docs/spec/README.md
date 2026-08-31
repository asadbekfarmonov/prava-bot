# prava-bot — Specification

`prava-bot` is a Telegram Mini App that prepares candidates for the **Uzbekistan
driving-license theory exam** (YHQ — Yo'l Harakati Qoidalari). It is adapted from the
SATStudy Bot architecture (FastAPI + React Telegram Mini App + PostgreSQL) with the domain
changed from SAT to the Uzbek theory test.

The product goal is a preparation experience **as close to the real exam as possible** —
same format, same media (photos **and** animations) — with **teaching explanations** on every
practice question.

## Source of truth for exam rules

Exam facts come from
[`research/uzbekistan-driving-license.md`](../../research/uzbekistan-driving-license.md)
(last verified 2026-08-31). If that research changes, update
[`01-exam-and-rules.md`](01-exam-and-rules.md) **and** the backend exam configuration in the
same change.

## Spec index

| File | Purpose |
| --- | --- |
| [00-overview.md](00-overview.md) | Vision, scope, MVP boundary, non-goals, metrics |
| [01-exam-and-rules.md](01-exam-and-rules.md) | Official YHQ format; **single-source exam config**; our-app vs real-exam wording |
| [02-domain-model.md](02-domain-model.md) | Entities: shared bank, translations, `Rule`, media, mock, practice, readiness |
| [03-features.md](03-features.md) | Practice, explanations, mistakes, road-sign trainer, mock (continuous timer), readiness, admin |
| [04-i18n.md](04-i18n.md) | Translation-ready schema; Uzbek Latin v1, Russian v2 |
| [05-architecture.md](05-architecture.md) | Reused stack, object-storage media, exam config (not env), migrations, deploy |
| [06-content-plan.md](06-content-plan.md) | Topic taxonomy, road-sign content, `Rule` governance, targets |
| [07-readiness.md](07-readiness.md) | Fully specified readiness algorithm, states, and gate |

## Locked v1 decisions

- **Category**: B only.
- **Language**: Uzbek (Latin) only; schema is translation-ready for Russian in v2.
- **Media**: static image, looping muted MP4/WebM video, and animated GIF — **stored in
  object storage**, served via **content-addressed** URLs (`/api/question-media/{id}/{hash}`).
- **One shared question bank**: practice and mocks use the same `Question` records. **No
  separate exam bank and no mock templates.**
- **Mock**: 20 random unique published questions (category + language matched, without
  replacement, snapshotted per attempt); **continuous** 25-minute server-authoritative timer
  (no pause/resume, auto-submit at expiry); 2–5 options; exactly one correct; **pass ≥18/20**;
  no hints/explanations during the mock.
- **Exam rules** live in a **single versioned domain config** (`app/domain/exam_config.py`),
  **not** environment variables; each `MockAttempt` snapshots them.
- **Practice** attempts are **repeatable** across sessions (`PracticeAnswer`); mock answers
  are unique per attempt (`MockAnswer`).
- **Rule provenance**: every publishable question links to one or more `Rule` records
  (`QuestionRule`); free-form strings are not the legal foundation.
- **Content**: original questions authored in the admin studio, each linked to its YHQ rule.
  No third-party bank import until reuse rights are confirmed.
- **Reuse from SATStudy**: streaks, daily goals, admin studio, onboarding.
- **Dropped from SATStudy**: adaptive exam modules/routing, SPR (type-in), 400–1600 score,
  mock templates, exam pause/resume, Desmos calculator.
- **Added vs SATStudy**: animation media + object storage, `Rule`/translation tables,
  mistakes review, road-sign trainer, readiness score.

## Deferred to v2

Leaderboards; situation trainer; spaced-repetition; exam-day checklist; Russian + Cyrillic;
additional categories (A/A1/C/D); Telegram reminder messages.
