# prava-bot — Specification

`prava-bot` is a Telegram Mini App that prepares candidates for the **Uzbekistan
driving-license theory exam** (YHQ — Yo'l Harakati Qoidalari). It is adapted from the SATStudy
Bot architecture (FastAPI + React Telegram Mini App + PostgreSQL), with the domain changed from
SAT to the Uzbek theory test.

Goal: a preparation experience **as close to the real exam as reasonably possible** — same
format, same media (photos **and** animations) — with **teaching explanations** on every
practice question.

## Source of truth for exam rules

Exam facts come from
[`research/uzbekistan-driving-license.md`](../../research/uzbekistan-driving-license.md)
(verified 2026-08-31). If it changes, update [`01-exam-and-rules.md`](01-exam-and-rules.md)
**and** the backend exam configuration in the same change.

## Spec index

| File | Purpose |
| --- | --- |
| [00-overview.md](00-overview.md) | Vision, scope, MVP boundary, non-goals, metrics |
| [01-exam-and-rules.md](01-exam-and-rules.md) | Official YHQ format; single-source exam config; verified vs unverified behaviour |
| [02-domain-model.md](02-domain-model.md) | Entities: immutable versions, translations, `Rule`, media, mock, practice, reports, roles |
| [03-features.md](03-features.md) | Practice, explanations, mistakes, sign trainer, mock, readiness, rankings, reports, admin |
| [04-i18n.md](04-i18n.md) | Translation-ready schema; Uzbek Latin v1, Russian v2 |
| [05-architecture.md](05-architecture.md) | Reused stack, immutable versions, object-storage media, exam config, security, migrations |
| [06-content-plan.md](06-content-plan.md) | Topic taxonomy, **explanation-quality standard**, rule governance, targets |
| [07-readiness.md](07-readiness.md) | Readiness algorithm, states, **curriculum-coverage gate**; diagnostic ≠ readiness |
| [08-admin.md](08-admin.md) | Admin dashboard, editor + live preview, Rule picker, roles/lifecycle, bulk ops, duplicates, reports, pre-publish QA |
| [09-security.md](09-security.md) | Threat model: auth, IDOR, admin, **exam-answer non-leak**, XSS/CSP, uploads, API, privacy, webhook, storage, tests |
| [10-ranking.md](10-ranking.md) | Learning-weighted server-side points, surfaces, privacy, anti-cheat |
| [11-content-acquisition.md](11-content-acquisition.md) | Official sources, existing products, partnership terms, original-content pipeline + asset system |
| [12-ui-exam-mode.md](12-ui-exam-mode.md) | Exam-focused UI; verified vs approximation; animation semantics |
| [13-deployment.md](13-deployment.md) | Railway production: single service, Postgres, Storage Bucket, webhook, /health, migrations, env |
| [14-theory-handbook.md](14-theory-handbook.md) | Theory/YHQ Handbook: sections, articles, content blocks, progress, favorites, search, admin, versioning, Theory↔Practice |
| [15-road-sign-catalogue.md](15-road-sign-catalogue.md) | Structured road-sign / marking / controller-gesture / traffic-light catalogues + search/filter |
| [16-frontend-redesign.md](16-frontend-redesign.md) | Full Mini App redesign: audit, bottom-nav, design tokens/system, all screens, states, Telegram UX, mock mode, a11y, plan |
| [17-product-expansion.md](17-product-expansion.md) | Competitor-density feature matrix + per-feature analysis + roadmap (Core / v1.1 / v2) |
| [18-theory-production-completion.md](18-theory-production-completion.md) | Finish Theory end-to-end: verified built-in content, complete visual catalogues, progress/favorites, Theory↔Practice, full Admin CRUD, archive/remove semantics, completeness tests |

## Locked v1 decisions

- **Production hosting: Railway** — one project with a **single application service** (FastAPI
  + aiogram **webhook** + built React Mini App + light jobs), **Railway PostgreSQL**, and the
  **Railway S3-compatible Storage Bucket**. Production uses **webhooks** (not long polling);
  Telegram webhook at `/telegram/webhook`; Railway healthcheck at `/health`; app binds `$PORT`.
  Details: [13-deployment.md](13-deployment.md).
- **Category** B only; **language** Uzbek (Latin) only; schema translation-ready for Russian.
- **One shared question bank**: practice and mocks use the same questions. **No separate exam
  bank, no mock templates.**
- **Immutable published `QuestionVersion`**: attempts pin the exact version shown; editing a
  published question creates a new version; historical mocks never change.
- **Media**: image / looping muted MP4/WebM / GIF (SVG rejected), stored in the **Railway
  S3-compatible Storage Bucket** (private) via an S3-compatible adapter, served via
  **content-addressed** URLs (`/api/media/{media_id}/{content_hash}`); immutable.
- **Mock**: 20 random unique published questions (category+language, without replacement,
  version-pinned, snapshotted per attempt); **continuous** 25-minute **server-authoritative**
  timer (no pause, auto-submit at expiry); 2–5 options; one correct; **pass ≥18/20**; **no
  hints and no correct-answer leak** during the mock; distinct exam-mode UI.
- **Exam rules** live in a **single versioned domain config** (`app/domain/exam_config.py`),
  **not** env vars; snapshotted per attempt. Readiness + ranking thresholds live there too.
- **Practice** attempts are **repeatable** (`PracticeAnswer`, version-pinned); mock answers are
  unique per attempt (`MockAnswer`).
- **Rule provenance**: `Rule` + `RuleTranslation` + `QuestionVersionRule` (snapshots
  `rule_version`); superseding a rule flips linked versions to `needs_reverification`.
- **Explanations** meet the explanation-quality standard and require human verification before
  publish.
- **Readiness**: data-gated; diagnostic is **not** readiness; "exam ready" requires
  **curriculum coverage** across all topics.
- **Rankings are v1**, server-computed, learning-weighted, farm-resistant; opt-out + custom
  display name; no location collection.
- **Roles**: `content_author`/`content_reviewer`/`admin`/`superadmin`, enforced server-side.
- **Content**: original authored questions unless licensed content is obtained; no scraping of
  third-party/official banks (visible ≠ reusable).

## Deferred to v2

Situation trainer; spaced-repetition; exam-day checklist; Russian + Cyrillic; additional
categories (A/A1/C/D); Telegram reminder messages; region/city ranking.
