# 05 — Architecture

## Reuse the SATStudy stack

prava-bot is a fork of the SATStudy Bot architecture:

- **Backend**: FastAPI + Uvicorn, SQLAlchemy 2, Alembic, psycopg 3 (PostgreSQL),
  pydantic-settings, itsdangerous signed sessions, aiogram 3 (Telegram bot that only
  launches the Mini App).
- **Frontend**: React + Vite + TypeScript, opened as a **Telegram Web App**. (katex is
  SAT-specific and likely dropped — driving questions rarely need formulae.)
- **Layout**: `app/api`, `app/bot`, `app/config`, `app/domain`, `app/services`,
  `app/storage`, `app/jobs`, `app/observability`, `app/scripts`; `frontend/`.
- **Auth**: Telegram Mini App **initData HMAC** honouring `TELEGRAM_INIT_DATA_MAX_AGE_SECONDS`;
  signed sessions via `SESSION_SECRET`; dev login gated to `APP_ENV=development`.

Build/deploy shape (Docker builds Vite → FastAPI serves it → Alembic migrates on startup →
binds Railway `PORT`) is reused.

## What is dropped

- Adaptive exam module routing (base/easy/hard, adaptive threshold).
- **Mock templates / fixed sets / a separate exam bank** — mocks are generated from the
  shared bank at start (see [03-features.md](03-features.md#mock-exam-simulation-maximum-real-exam-fidelity)).
- **Pause/resume** for exams (the mock timer is continuous — below).
- Student-produced-response (type-in) questions and numeric grading.
- 400–1600 SAT scoring and section-score estimation.
- `Section` (math/reading_writing).
- The Desmos calculator and its isolated `/desmos-frame` CSP (SAT-specific).

## What is added / changed

- `Category` + controlled `Topic`; translation tables (`QuestionTranslation`,
  `AnswerOptionTranslation`); `Rule`/`QuestionRule`.
- **Object-storage media pipeline** with content-addressed URLs (below).
- `PracticeSession`/`PracticeAnswer` (repeatable) split from `MockAnswer` (unique per
  attempt); `MockAttempt`/`MockQuestion`/`MockAnswer`.
- **Single-source exam configuration** in `app/domain/exam_config.py` (below).
- Readiness service ([07-readiness.md](07-readiness.md)).
- Road-sign trainer (uses the shared question bank; no new content pipeline).

## Exam configuration (single source of truth, not env)

Legal exam rules (question count, time limit, pass threshold, option bounds) are **domain
configuration**, defined **once** in `app/domain/exam_config.py` as versioned constants
(optionally mirrored to a read-only `exam_config` table for audit). Readiness thresholds
live in the same place.

- **Do NOT** put these in environment variables. Specifically, there are **no**
  `MOCK_QUESTION_COUNT`, `MOCK_TIME_LIMIT_SECONDS`, or `MOCK_PASS_CORRECT_B` env vars.
- Each `MockAttempt` **snapshots** the applicable config (`exam_config_version`,
  `question_count`, `time_limit_seconds`, `pass_correct`) at start so historical attempts
  stay interpretable after a rule change.
- Deployment/infra config (DB URL, object-storage creds, session/webhook secrets, admin ids,
  rate limits) remains in env — that is the correct place for **deployment** config, not
  legal rules.

## Media pipeline (object storage + content-addressed URLs)

- **Bytes live in S3-compatible object storage** (Cloudflare R2 / AWS S3 / MinIO). Postgres
  stores only `QuestionMedia` metadata: `media_type`, `content_type`, `content_hash`
  (sha256), `storage_key`, optional `poster_hash`, dimensions, `duration_ms`, `byte_size`
  (see [02-domain-model.md](02-domain-model.md#media-metadata-in-db-bytes-in-object-storage)).
- **Upload (admin only)**:
  - **Image** → re-encode to WebP (reuse SATStudy's Pillow path), enforce dimension/size caps.
  - **GIF** → validate as an image with Pillow; enforce size/frame/pixel limits; keep animation.
  - **Video** (`mp4`/`webm`) → **sniff the container/codec from the bytes** (never trust the
    client `Content-Type`); enforce a max file size and, where feasible, max duration; reject
    anything not directly web-playable (**no server-side transcoding in v1**); generate a
    **poster** still (first frame).
  - Compute `content_hash`, store bytes under `storage_key`, persist metadata.
- **Serving**: content-addressed URL `/api/question-media/{media_id}/{content_hash}` (the API
  streams from object storage, or redirects to a signed object-storage URL). Because the hash
  changes when media is replaced, the URL changes too — so `Cache-Control: public,
  max-age=31536000, immutable` is **safe** and never serves stale media. **Do not** use a
  by-question-id URL with immutable caching (that was the stale-media bug this design fixes).
  Draft-question media is admin-only; published media is world-cacheable behind the hash.
- **Video playback**: served with `Accept-Ranges`/range support (native to most object
  stores) for seeking.

### DB-media MVP fallback (explicit tradeoff)

If, for MVP speed, we temporarily store bytes in Postgres (as SATStudy did for images):
- it is acceptable **only** for images/GIFs and **small** clips;
- the URL is still content-addressed (`.../{media_id}/{content_hash}`) so caching stays safe;
- **object storage becomes mandatory** once any of: total media > ~1 GB, any single video
  > ~5 MB, or video is used at scale. Videos should go to object storage from day one if at
  all possible. This threshold is documented so the migration is deliberate, not accidental.

### CSP implications (main.py)

Add **`media-src 'self'`** so inline `<video>`/GIF load. If media is served from a distinct
object-storage/CDN host, add that host to `media-src`/`img-src` explicitly (exact-match host,
no wildcards beyond the provider domain). Remove the SAT-specific `/desmos-frame` policy.

## Frontend rendering

- A `QuestionMedia` component selects the element by `media_type`:
  - `image`/`gif` → `<img>`;
  - `video` → `<video autoplay muted loop playsinline preload="metadata" poster=...>` with a
    manual replay button and a reduced-motion fallback to the poster.
- Practice and post-exam review render explanations + rule; the **live mock does not**.

## Mock timer (server-authoritative, continuous)

- `MockAttempt.expires_at = started_at + time_limit_seconds` is the **only** authority.
- Remaining time on any load = `expires_at - now` (server clock). Client timers are display
  only and can never extend the deadline.
- **No pause endpoint.** Closing the app does not stop the clock.
- **Auto-submit** occurs server-side when `now >= expires_at` (lazily on next access, and/or
  via a sweep job in `app/jobs/`); grading is deterministic.
- Offline answers are buffered client-side and synced on reconnect; late syncs past
  `expires_at` do not change the result. See
  [03-features.md](03-features.md#network-loss-behaviour).

## Security

- Telegram initData HMAC + max-age; never trust client-supplied user ids.
- Dev login only when `APP_ENV=development` and `DEV_AUTH_ENABLED=true`.
- Admin endpoints gated by `ADMIN_TELEGRAM_IDS`; media upload is admin-only, size-limited,
  content-sniffed.
- Sessions signed with `SESSION_SECRET`; production validators (no default secret, no debug,
  https `MINI_APP_URL`, distinct webhook secret) reused from SATStudy.
- Object-storage credentials in env/secret manager; served responses keep
  `X-Content-Type-Options: nosniff`.
- Rate limiting reused for auth/write/admin scopes.

## Config / env

- **Deployment env (allowed)**: `APP_ENV`, `APP_DEBUG`, `DATABASE_URL`, `BOT_TOKEN`,
  `BOT_USERNAME`, `SESSION_SECRET`, `TELEGRAM_WEBHOOK_ENABLED/SECRET`, `ADMIN_TELEGRAM_IDS`,
  `MINI_APP_URL`, `DEV_AUTH_ENABLED`, `TELEGRAM_INIT_DATA_MAX_AGE_SECONDS`, rate-limit vars,
  and **object storage**: `MEDIA_STORAGE_BUCKET`, `MEDIA_STORAGE_ENDPOINT`,
  `MEDIA_STORAGE_ACCESS_KEY`, `MEDIA_STORAGE_SECRET_KEY`, `MEDIA_PUBLIC_BASE_URL`, plus upload
  caps (`MAX_IMAGE_BYTES`, `MAX_VIDEO_BYTES`).
- **Domain config (NOT env)**: exam rules and readiness thresholds live in
  `app/domain/exam_config.py`. Removed: SAT exam-sizing vars, `DESMOS_API_KEY`, and any
  `MOCK_*` legal-rule vars.

## Migrations

Fresh Alembic history for prava-bot's schema (new DB, not a SATStudy migration chain). Every
model change ships a migration; `alembic upgrade head` must apply cleanly on startup and in
the pre-push gate.

## Deployment

- **New, separate** Railway service, **new bot token**, **new Postgres DB**, **object-storage
  bucket** — fully independent from SATStudy.
- Same Dockerfile pattern. Seed script in `app/scripts/` loads the initial authored bank
  (questions + translations + rules + media metadata).

## Testing

- `pytest`: auth; onboarding/practice flow (repeatable `PracticeAnswer`); mistakes review;
  mock flow fidelity (20 questions, snapshotted config, `expires_at` continuity, no pause,
  server auto-submit at expiry, offline-sync-after-expiry ignored, pass at 18); shared-bank
  selection (unique/without-replacement, category+language filter, no regeneration on reopen);
  Rule provenance required to publish; media upload/serve (image/gif/video validation,
  content-hash URL, oversize rejection, draft auth); readiness states (insufficient/initial/
  ready + gate); admin gating; security hardening.
- Playwright e2e: practice loop, media rendering, road-sign trainer, timed mock.
