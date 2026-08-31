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
Mini App. A **Railway Cron** sweep (every 15 min) finalizes abandoned/expired attempts as a
**backstop only (cleanup)** — an expired attempt is finalized immediately the next time it is
accessed, and correctness never depends on the cron running on time. See
[05-architecture.md](05-architecture.md#mock-timer--integrity-server-authoritative) and
Scheduled maintenance (below).

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

# Media storage adapter — Railway S3-compatible Storage Bucket (locked names):
BUCKET=...
ACCESS_KEY_ID=...
SECRET_ACCESS_KEY=...
REGION=...
ENDPOINT=...
MEDIA_PUBLIC_BASE_URL=...            # optional CDN/base for presigned/download URLs
MAX_IMAGE_BYTES=...
MAX_VIDEO_BYTES=...
MAX_VIDEO_DURATION_MS=...            # optional
```

The `MediaStorage` adapter reads exactly these five keys (`BUCKET`, `ACCESS_KEY_ID`,
`SECRET_ACCESS_KEY`, `REGION`, `ENDPOINT`) from one central config; migrating to R2/S3 only
changes their values.

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

## Domain & TLS

- Production domain: **`app.prava.uz`**, with **Railway-managed TLS**.
- `MINI_APP_URL=https://app.prava.uz`; the Telegram webhook is registered to
  `https://app.prava.uz/telegram/webhook`.

## Scheduled maintenance (Railway Cron)

Both are **cleanup/backstop** jobs — never authoritative for correctness:

- **Expired-mock sweep — every 15 min**: finalizes abandoned/expired `MockAttempt`s that were
  never reopened. Request-time enforcement (`now >= expires_at → finalize`) remains the
  authority; this cron only catches attempts no one touched again.
- **Orphan-media cleanup — daily**: deletes bucket objects + `QuestionMedia` rows not
  referenced by any question version, **after the 30-day grace period** (below).

## Backups & retention

**PostgreSQL**:
- daily Railway backup, **6-day** retention;
- weekly backup, **1-month** retention;
- monthly backup, **3-month** retention;
- **PITR** enabled (~4-week window);
- an additional **daily logical `pg_dump`** (independent of Railway snapshots).

**Media (bucket)**:
- assets are **immutable/versioned** (content-addressed); replacing media creates a new object.
- **No hard delete while an object is still referenced** by any question version.
- **Orphan grace period: 30 days** — unreferenced objects are only removed by the daily cron
  after 30 days.
- **Offsite mirror**: planned later (a second-region/provider copy), not v1.

## Resolved deployment decisions

Domain (`app.prava.uz`) + Railway TLS; media = Railway bucket via S3 adapter
(`BUCKET`/`ACCESS_KEY_ID`/`SECRET_ACCESS_KEY`/`REGION`/`ENDPOINT`); migrations = startup Alembic
for single-instance v1, dedicated migration/release phase when multi-instance; maintenance via
Railway Cron (15-min mock sweep, daily orphan cleanup); backups + retention as above; media
orphan grace 30 days.

## Remaining open items (revisit later, not blocking v1)

1. **Offsite media mirror** — provider/region and cadence when we add it.
2. **Multi-instance cutover** — the exact traffic point at which we move from startup-Alembic to
   the dedicated migration/release phase.
