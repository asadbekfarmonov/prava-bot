# 13 — Deployment (Railway)

Production hosting is **Railway**. One Railway project holds the application, PostgreSQL, and
media storage. This spec is the single source for the production deployment design.

## Railway project layout

```
prava-bot  (Railway project)
├── Application service
│   ├── FastAPI backend (REST API)
│   ├── aiogram Telegram bot — WEBHOOK (no long polling in production)
│   ├── React/Vite Telegram Mini App (built, served by FastAPI)
│   └── lightweight background jobs (e.g. stale-mock sweep, orphan-media cleanup)
├── PostgreSQL              (application/domain data — see 02-domain-model.md)
└── S3-compatible Storage Bucket   (media bytes: images, sign images, GIFs, MP4/WebM, posters)
```

**One application service** for v1 (bot + API + frontend + jobs together). Split into separate
services only if scale later requires it. Media bytes live only in the bucket; **never** in a
Railway Volume and **never** in PostgreSQL (Postgres stores media *metadata* only).

## Application routes

```
/                        React Telegram Mini App (built assets, SPA fallback)
/api/*                   REST API
/api/media/{media_id}/{content_hash}   content-addressed media (stream or presigned redirect)
/telegram/webhook        Telegram Bot API webhook (production)
/health                  Railway healthcheck
```

## Healthcheck

- `/health` returns 200 only when the app is ready (process up; DB reachable).
- Railway must be configured with `/health` as the **healthcheck path**; a new deployment
  **does not receive production traffic until `/health` succeeds**.

## Port binding

The app **binds Railway's provided `PORT`** at runtime; the port is never hard-coded.

## Deployment lifecycle

```
GitHub main
→ Railway deployment triggered
→ Docker build (Vite frontend build → FastAPI application image)
→ Alembic migrations run
→ application starts, binds $PORT
→ /health succeeds
→ deployment receives traffic
```

Merging to `main` deploys to production; prefer a feature branch + PR flow.

## Database migrations (safe strategy)

- **v1 (single instance)**: run `alembic upgrade head` on startup before serving. Simple and
  correct for one instance.
- **When scaling to multiple instances**: startup migrations race. Use a **dedicated release
  step** (Railway release/pre-deploy command) that runs migrations **once** before new
  instances start, **or** guard startup migrations with a Postgres **advisory lock** so only
  one instance migrates and others wait. Migrations must be written to be **safe to run during
  deployment** (backward-compatible: additive columns/tables first, backfill, then drops in a
  later release — no destructive change that breaks the currently-running version).

## Telegram bot & webhook

- The bot is **thin** ([03-features.md](03-features.md) / [00-overview.md](00-overview.md)):
  `/start` → welcome + a button that opens the Mini App. The full learning UI lives in the Mini
  App, not in chat. Future (deferred) bot messages: daily/streak/exam-date reminders, weekly
  ranking result, "take a mock" nudge.
- **Production uses webhooks, not long polling.** On startup the app registers the webhook to
  `https://<public-domain>/telegram/webhook` (e.g. `https://app.prava.uz/telegram/webhook`) and
  sets the menu-button Web App URL to `MINI_APP_URL`.
- Webhook requests are authenticated with `TELEGRAM_WEBHOOK_SECRET`
  (`X-Telegram-Bot-Api-Secret-Token`, constant-time compare); spoofed requests are rejected.
  The secret must differ from `SESSION_SECRET`. See
  [09-security.md](09-security.md#webhook--bot).

## Media storage on Railway

- Provider: **Railway S3-compatible Storage Bucket** (production v1). Accessed only through the
  **`MediaStorage` / `S3CompatibleMediaStorage`** adapter
  ([05-architecture.md](05-architecture.md#storage-adapter-portability)) so a future move to
  Cloudflare R2 / AWS S3 changes only configuration.
- Bucket is **private**. Published media is served via the content-addressed
  `/api/media/{media_id}/{content_hash}` route (stream or short-lived presigned GET); draft
  media requires admin auth. Admin uploads use a validated presigned PUT or backend-proxied
  upload; storage keys are server-generated. Full controls:
  [09-security.md](09-security.md#object-storage).

## Mock expiry on Railway (no exact-time scheduler dependency)

The authoritative rule is `expires_at = started_at + time_limit_seconds`. Correctness must
**not** depend on a job firing at exactly second 1500. Every request touching an in-progress
attempt first checks:

```
if now >= attempt.expires_at:
    finalize_attempt()   # grade server-side, mark completed
```

This applies to: loading the current mock, saving an answer, manual submit, and reopening the
Mini App. A **lightweight sweep job** may periodically finalize abandoned/expired attempts, but
it is only a backstop — an expired attempt is finalized immediately the next time it is
accessed. See [05-architecture.md](05-architecture.md#mock-timer--integrity-server-authoritative).

## Environment variables (deployment/runtime only)

Legal exam rules are **domain config**, not env (see below). Deployment env:

```
APP_ENV=production
APP_DEBUG=false
DATABASE_URL=...                     # Railway PostgreSQL

BOT_TOKEN=...
BOT_USERNAME=...
TELEGRAM_WEBHOOK_SECRET=...          # must differ from SESSION_SECRET
TELEGRAM_WEBHOOK_ENABLED=true

SESSION_SECRET=...                   # >= 32 chars, unique
TELEGRAM_INIT_DATA_MAX_AGE_SECONDS=...
MINI_APP_URL=https://app.prava.uz
ADMIN_TELEGRAM_IDS=...
DEV_AUTH_ENABLED=false               # dev login unavailable in production

# Media storage adapter (Railway bucket; names may vary by Railway integration —
# the storage adapter centralizes configuration):
MEDIA_STORAGE_ENDPOINT=...
MEDIA_STORAGE_BUCKET=...
MEDIA_STORAGE_ACCESS_KEY=...
MEDIA_STORAGE_SECRET_KEY=...
MEDIA_PUBLIC_BASE_URL=...            # optional CDN/base for presigned/download URLs
MAX_IMAGE_BYTES=...
MAX_VIDEO_BYTES=...
MAX_VIDEO_DURATION_MS=...            # optional
```

Exact Railway-provided bucket variable names may differ; the `MediaStorage` adapter reads them
from one central config so only the adapter changes if names differ.

### NOT environment variables (domain config)

Legal exam rules live in `app/domain/exam_config.py`
([01-exam-and-rules.md](01-exam-and-rules.md)), versioned and snapshotted per attempt. Do
**not** add `MOCK_QUESTION_COUNT`, `MOCK_TIME_LIMIT_SECONDS`, or `MOCK_PASS_CORRECT_B`. These
stay domain config: `questions=20`, `time_limit_seconds=1500`, `minimum_correct=18`,
`answer_options_min=2`, `answer_options_max=5`. Readiness ([07](07-readiness.md)) and ranking
([10](10-ranking.md)) thresholds also live there.

## Admin in the same deployment

Admin UI (`/admin/*` in the React app) ships in the same service, but **every** admin API
enforces server-side authorization: authenticated Telegram user + `AdminRole` + required
permission ([08-admin.md](08-admin.md), [09-security.md](09-security.md#admin-security)).
Hidden frontend routes are never a security control.

## Open deployment/ops questions (need a product/ops decision)

1. Final production domain (`app.prava.uz` assumed) and DNS/TLS on Railway.
2. Exact Railway bucket integration + its provided env var names (adapter absorbs the diff).
3. When to switch startup migrations → release-phase/advisory-lock (i.e. when we go multi-instance).
4. Whether the stale-mock sweep + orphan-media cleanup run in-process (asyncio task) or as a
   separate Railway cron/service.
5. Backup/retention policy for Postgres and the bucket.
