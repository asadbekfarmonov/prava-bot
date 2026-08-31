# prava-bot — Specification

`prava-bot` is a Telegram Mini App that prepares candidates for the **Uzbekistan
driving-license theory exam** (YHQ — Yo'l Harakati Qoidalari). It is adapted from
the SATStudy Bot architecture (FastAPI + React Telegram Mini App + PostgreSQL) with
the domain changed from SAT to the Uzbek theory test.

The product goal is a preparation experience that is **as close to the real exam as
possible** — same format, same media (photos **and** animations) — with **teaching
explanations** on every practice question.

## Source of truth for the exam rules

All exam facts in these specs come from
[`research/uzbekistan-driving-license.md`](../../research/uzbekistan-driving-license.md)
(last verified 2026-08-31). If that research is updated, update
[`01-exam-and-rules.md`](01-exam-and-rules.md) to match.

## Spec index

| File | Purpose |
| --- | --- |
| [00-overview.md](00-overview.md) | Vision, scope, MVP boundary, non-goals, success metrics |
| [01-exam-and-rules.md](01-exam-and-rules.md) | Official YHQ theory format, pass rule, categories, key facts |
| [02-domain-model.md](02-domain-model.md) | Entities and data model, including the media model |
| [03-features.md](03-features.md) | Practice, mistakes review, mock exam, readiness, admin studio |
| [04-i18n.md](04-i18n.md) | Language strategy (Uzbek Latin v1, Russian later) |
| [05-architecture.md](05-architecture.md) | Reused SATStudy stack, media pipeline, deployment, migrations |
| [06-content-plan.md](06-content-plan.md) | Topic taxonomy, question targets, authoring workflow |

## Locked v1 decisions

- **Category**: B only.
- **Language**: Uzbek (Latin script) only. Russian and Cyrillic deferred to v2.
- **Media**: static image, looping muted MP4/WebM video, and animated GIF.
- **Exam fidelity**: 20 questions, single 25-minute timer, 2–5 options, exactly one
  correct, **pass at ≥18/20** (max 2 mistakes). No hints or explanations during the mock.
- **Practice**: immediate feedback with per-option explanations and a YHQ rule reference.
- **Content**: original questions authored in the admin studio, each tagged with the
  rule it teaches. No import of a third-party question bank until reuse rights are confirmed.
- **Reuse from SATStudy**: streaks, daily goals, leaderboards, onboarding, admin studio.
- **Dropped from SATStudy**: adaptive exam modules/routing, student-produced-response
  (type-in) questions, the 400–1600 score model.
- **Added vs SATStudy**: animation media, mistakes review queue, readiness score.

## Deferred to v2

Road-sign card trainer, situation trainer, spaced-repetition scheduling,
exam-day process checklist, Russian + Cyrillic, additional categories (A/A1/C/D).
