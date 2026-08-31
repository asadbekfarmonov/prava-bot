# 05 — Architecture

## Reuse the SATStudy stack

- **Backend**: FastAPI + Uvicorn, SQLAlchemy 2, Alembic, psycopg 3 (PostgreSQL),
  pydantic-settings, itsdangerous signed sessions, aiogram 3 (bot only launches the Mini App).
- **Frontend**: React + Vite + TypeScript as a **Telegram Web App**. (katex is SAT-specific;
  likely dropped.)
- **Layout**: `app/api`, `app/bot`, `app/config`, `app/domain`, `app/services`, `app/storage`,
  `app/jobs`, `app/observability`, `app/scripts`; `frontend/`.
- **Auth**: Telegram Mini App **initData HMAC** + max-age; signed sessions via
  `SESSION_SECRET`; dev login gated to `APP_ENV=development`. Full controls:
  [09-security.md](09-security.md).

Build/deploy shape (Docker builds Vite → FastAPI serves it → Alembic migrates → binds Railway
`PORT`) is reused.

## Dropped from SATStudy

Adaptive routing; **mock templates / fixed sets / separate exam bank**; **pause/resume**; SPR
(type-in); 400–1600 scoring; `Section`; Desmos calculator + `/desmos-frame` CSP.

## Added / changed

- `Category` + controlled `Topic`; **immutable `QuestionVersion`** with version-keyed
  translations; `AnswerOption` per version.
- `Rule` + `RuleTranslation` + `QuestionVersionRule` (snapshotting `rule_version`);
  `QuestionVersionSource`.
- **Object-storage media** (content-addressed, immutable) + `QuestionMediaTranslation`.
- `PracticeSession`/`PracticeAnswer` (repeatable, version-pinned) vs `MockAnswer` (unique per
  attempt); `MockAttempt`/`MockQuestion` (version-pinned).
- **Single-source exam configuration** in `app/domain/exam_config.py`.
- Readiness ([07-readiness.md](07-readiness.md)); **ranking** ([10-ranking.md](10-ranking.md));
  road-sign trainer; content **reports**; **admin roles** ([08-admin.md](08-admin.md)).

## Immutable question versions (integrity)

A `MockQuestion`/`MockAnswer`/`PracticeAnswer` references a **`question_version_id`**, never a
live question. Once a `QuestionVersion` is published or referenced by any attempt it is
**never mutated**; edits create a new version and repoint `Question.current_version_id`. This
guarantees a mock in progress or a historical mock review always shows exactly what the user
saw. When a linked `Rule` is superseded, affected versions flip to `needs_reverification`
(admin surfaces them) — the historical attempts still render their pinned version.

## Exam configuration (single source of truth, not env)

Legal exam rules (question count, time limit, pass threshold, option bounds) and readiness/
ranking thresholds live **once** in `app/domain/exam_config.py` (optionally mirrored to a
read-only table for audit). **Never** in env vars — there are **no** `MOCK_QUESTION_COUNT`,
`MOCK_TIME_LIMIT_SECONDS`, or `MOCK_PASS_CORRECT_B` vars. Each `MockAttempt` snapshots the
applicable values (`exam_config_version`, `question_count`, `time_limit_seconds`,
`pass_correct`). Deployment config (DB/storage creds, secrets, admin ids, rate limits) stays
in env.

## Media pipeline (Railway Storage Bucket, content-addressed, immutable)

- **Production v1 provider: the Railway S3-compatible Storage Bucket** (same project as the
  app + Postgres). Not R2/S3/MinIO — but accessed only through an **S3-compatible
  abstraction** so those remain migration options (see storage adapter + [13-deployment.md](13-deployment.md)).
  Postgres holds `QuestionMedia` metadata + `content_hash` + `storage_key`/`poster_storage_key`.
  **Do not** use a Railway Volume for media and **do not** store media bytes in Postgres.
- **Upload (admin only)**: sniff type from bytes (never trust client `Content-Type`);
  **reject SVG**; images → WebP; validate GIF (frame/pixel caps); validate video
  container/codec, size, duration; **no server transcoding v1**; generate a first-frame poster
  for video; compute `content_hash`; write to a **private, server-generated storage key**. Full
  upload threat model: [09-security.md](09-security.md#media-upload-security). Admin upload may
  use a **presigned PUT** (backend issues the URL, then validates + confirms the hash before the
  media becomes usable) or backend-proxied upload.
- **Serving**: content-addressed `/api/media/{media_id}/{content_hash}`. The backend resolves
  metadata, checks visibility, then **streams the object or redirects to a short-lived presigned
  GET**. Hash changes on replacement → new URL, so `Cache-Control: public, max-age=31536000,
  immutable` is safe (no stale media). **Do not** use `/api/questions/{id}/media` with immutable
  caching. Draft media is admin-only (private, streamed or short-lived presigned); published
  media is cacheable behind the hash. Video served with range support.
- Railway buckets are **private**: least-privilege creds, no public listing, no overwrite of
  immutable objects, orphan-cleanup job ([09-security.md](09-security.md#object-storage)).

### Storage adapter (portability)

Domain/business code never talks to Railway directly. Define a `MediaStorage` port:

```
MediaStorage
  put(key, bytes, content_type)
  get(key) -> stream
  delete(key)
  create_download_url(key, ttl) -> presigned GET
  create_upload_url(key, constraints, ttl) -> presigned PUT
```

Production implementation: **`S3CompatibleMediaStorage`** configured for the Railway bucket
via `MEDIA_STORAGE_*` env. Migrating to R2/S3 changes only adapter configuration, not domain
code.

### DB-media MVP fallback (explicit tradeoff)

Temporarily storing bytes in Postgres is acceptable **only** for images/GIFs and small clips;
the URL stays content-addressed. The Railway bucket is the default from day one; videos must
never live in Postgres. Bucket becomes strictly required once any of: total media > ~1 GB,
any single video > ~5 MB, or video at scale.

### CSP

`default-src 'self'`; add **`media-src 'self'`** (+ object-storage/CDN host, exact match, if
distinct); `img-src 'self' data: <media host>`; `script-src 'self' https://telegram.org`;
`frame-ancestors` Telegram; `object-src 'none'`; `base-uri 'self'`. Remove the SAT
`/desmos-frame` policy.

## Frontend rendering

`QuestionMedia` component: `image`/`gif` → `<img>`; `video` → `<video autoplay muted loop
playsinline preload="metadata" poster=...>` with a minimal replay control and reduced-motion
fallback. Practice/review render explanations + rule; **exam mode does not**
([12-ui-exam-mode.md](12-ui-exam-mode.md)).

## Mock timer & integrity (server-authoritative)

`expires_at = started_at + time_limit_seconds` is the only authority; remaining =
`expires_at - now`; no pause; **auto-submit** server-side at expiry (lazily on next access
and/or a sweep job in `app/jobs/`); grading is deterministic and server-side. The live-mock
API returns **no** correctness/explanations and uses non-revealing option ids
([09-security.md](09-security.md#exam-integrity-critical)).

## Security

Full threat model in [09-security.md](09-security.md): Telegram auth/replay/session rotation;
server-side authorization + IDOR on every resource; role-based admin; exam-answer non-leak;
XSS (plain-text content, no raw HTML) + CSP; media-upload hardening (SVG rejected); API
(CSRF/CORS/rate-limit/mass-assignment/size/pagination/error-leak); privacy/data-minimization
(no phone number); webhook secret; object-storage ACL; explicit security tests.

## Config / env

- **Deployment env**: `APP_ENV`, `APP_DEBUG`, `DATABASE_URL`, `BOT_TOKEN`, `BOT_USERNAME`,
  `SESSION_SECRET`, `TELEGRAM_WEBHOOK_ENABLED/SECRET`, `ADMIN_TELEGRAM_IDS`, `MINI_APP_URL`,
  `DEV_AUTH_ENABLED`, `TELEGRAM_INIT_DATA_MAX_AGE_SECONDS`, rate-limit vars; object storage:
  `MEDIA_STORAGE_BUCKET/ENDPOINT/ACCESS_KEY/SECRET_KEY`, `MEDIA_PUBLIC_BASE_URL`, upload caps
  `MAX_IMAGE_BYTES`/`MAX_VIDEO_BYTES`/`MAX_VIDEO_DURATION_MS`.
- **Domain config (NOT env)**: exam rules + readiness + ranking thresholds in
  `app/domain/exam_config.py`. `admin` allowlist is env (`ADMIN_TELEGRAM_IDS`) but effective
  capability is the `AdminRole` resolved server-side.

## Migrations

Fresh Alembic history (new DB). Every model change ships a migration; `alembic upgrade head`
must apply cleanly on startup and in the pre-push gate.

## Deployment (Railway — see 13-deployment.md)

**Production hosting is Railway**, one project containing a **single application service**
(FastAPI backend + aiogram **webhook** + built React Mini App + lightweight jobs),
**Railway PostgreSQL**, and the **Railway S3-compatible Storage Bucket**. Split services later
only if scale requires it. New bot token, new DB, new bucket — independent from SATStudy.

Application routes:

```
/                    React Telegram Mini App (built assets)
/api/*               REST API
/api/media/{id}/{hash}   content-addressed media (stream or presigned redirect)
/telegram/webhook    Telegram Bot API webhook (production uses webhooks, NOT long polling)
/health              Railway healthcheck (traffic only after it succeeds)
```

Lifecycle: GitHub `main` → Railway build (Docker: Vite build → FastAPI image) → Alembic
migrate → app starts → `/health` succeeds → receives traffic. The app **binds Railway's
`PORT`** (never hard-coded). Full deployment/lifecycle/migration-safety detail lives in
[13-deployment.md](13-deployment.md). Seed script in `app/scripts/` loads the initial bank.

## Testing

`pytest`: auth; practice (repeatable, version-pinned); mistakes; mock fidelity (20 q,
snapshotted config, `expires_at` continuity, no pause, server auto-submit, offline-sync-past-
expiry ignored, pass at 18); **version immutability** (edit after publish → new version;
historical mock renders old version); shared-bank selection (unique/without-replacement,
category+language, no regeneration); rule provenance + `needs_reverification` propagation;
readiness states + coverage gate; ranking points/anti-cheat ([10-ranking.md](10-ranking.md));
media upload/serve (type sniff, SVG reject, oversize, content-hash URL, draft auth); the full
security suite ([09-security.md](09-security.md#security-tests-explicit)). Playwright e2e:
practice loop, media rendering, sign trainer, exam mode.
