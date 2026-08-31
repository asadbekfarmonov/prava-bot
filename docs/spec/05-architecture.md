# 05 — Architecture

## Reuse the SATStudy stack

prava-bot is a fork of the SATStudy Bot architecture:

- **Backend**: FastAPI + Uvicorn, SQLAlchemy 2, Alembic, psycopg 3 (PostgreSQL),
  pydantic-settings, itsdangerous signed sessions, aiogram 3 (Telegram bot that only
  launches the Mini App).
- **Frontend**: React + Vite + TypeScript, opened as a **Telegram Web App**; katex only if
  a question needs formulae (rare for driving — likely droppable).
- **Layout**: `app/api`, `app/bot`, `app/config`, `app/domain`, `app/services`,
  `app/storage`, `app/jobs`, `app/observability`, `app/scripts`; `frontend/`.
- **Auth**: Telegram Mini App **initData HMAC** validation honouring
  `TELEGRAM_INIT_DATA_MAX_AGE_SECONDS`; signed sessions via `SESSION_SECRET`; dev login
  gated to `APP_ENV=development`.

The build/deploy shape (Docker image builds Vite, FastAPI serves it, Alembic runs on
startup, binds Railway `PORT`) is reused verbatim.

## What is dropped

- Adaptive exam module routing (`ExamModuleRoute`, base/easy/hard, adaptive threshold).
- Student-produced-response (type-in) questions and numeric grading.
- 400–1600 SAT scoring and section score estimation.
- `Section` (math/reading_writing) concept.

## What is added / changed

- `Category` and controlled `Topic` in place of `Section`/free-text topic.
- **Media pipeline** for image **and** video/GIF (below).
- `MistakeEntry` + mistakes-review endpoints.
- Readiness computation (backend service) + dashboard endpoint.
- Single-module `MockTemplate`/`MockAttempt` with pass/fail.
- i18n string catalog (see [04-i18n.md](04-i18n.md)).

## Media pipeline

SATStudy stores images as compressed WebP bytes in Postgres (`QuestionImage`) and serves
them via `GET /api/questions/{id}/image` with private long-cache and admin-only access for
drafts. prava-bot generalises this to `QuestionMedia` (see
[02-domain-model.md](02-domain-model.md#questionmedia)):

- **Image** (`image/*` → re-encoded to WebP): reuse the existing Pillow compression path
  (`app/services/images.py`), max dimension + size cap unchanged.
- **GIF** (`image/gif`): validate with Pillow (it is an image), enforce size/frame/pixel
  limits; store as-is (do not flatten to a single frame). Guard against decompression bombs.
- **Video** (`video/mp4`, `video/webm`): validate by sniffing the container/codec from the
  bytes (do **not** trust the client `Content-Type`); enforce a **max file size**
  (e.g. 8–15 MB, config-driven) and, where feasible, a max duration. Store bytes in Postgres
  like images for v1 simplicity; generate a **poster** still (first frame) for the UI.
  - v1 accepts already-web-ready MP4(H.264)/WebM(VP9). **No server-side transcoding** in v1
    (heavy); reject anything that is not directly playable. Transcoding/object storage is a
    v2 scaling item.
- **Serving**: `GET /api/questions/{id}/media` returns bytes with the stored `content_type`,
  `Cache-Control: private, max-age=31536000, immutable`, and (for video) `Accept-Ranges`
  handling for seeking. Draft media is admin-only, matching SATStudy image auth.

### CSP implications (main.py)

SATStudy's strict CSP has no `media-src`. Add **`media-src 'self'`** (and `img-src`
already allows `data:`) so inline `<video>`/GIF from same-origin load. Video is same-origin
(served by our API), so no third-party host is added. The existing isolated `/desmos-frame`
policy is SAT-specific and can be **removed** (no calculator in a driving app).

## Frontend rendering

- A `QuestionMedia` component picks the element by `media_type`:
  - `image`/`gif` → `<img>`;
  - `video` → `<video autoplay muted loop playsinline preload="metadata" poster=...>`
    with a manual replay button and reduced-motion fallback to the poster.
- Practice and post-exam review render explanations + rule refs; the live mock does not.

## Security

Carry over SATStudy's protections and apply the SAT-app security notes:
- Telegram initData HMAC + max-age; never trust client-supplied user ids.
- Dev login only when `APP_ENV=development` and `DEV_AUTH_ENABLED=true`.
- Admin endpoints gated by `ADMIN_TELEGRAM_IDS`.
- Sessions signed with `SESSION_SECRET`; production validators (no default secret, no debug,
  https `MINI_APP_URL`, distinct webhook secret) reused from SATStudy settings.
- Media upload endpoints are **admin-only**, size-limited, and content-sniffed to prevent
  malicious uploads; served media sets `X-Content-Type-Options: nosniff` (already global).
- Rate limiting reused for auth/write/admin scopes.

## Config / env

Reuse SATStudy env with driving-specific additions:
- Existing: `APP_ENV`, `APP_DEBUG`, `DATABASE_URL`, `BOT_TOKEN`, `BOT_USERNAME`,
  `SESSION_SECRET`, `TELEGRAM_WEBHOOK_ENABLED/SECRET`, `ADMIN_TELEGRAM_IDS`, `MINI_APP_URL`,
  `DEV_AUTH_ENABLED`, `TELEGRAM_INIT_DATA_MAX_AGE_SECONDS`, rate-limit vars.
- New: `MOCK_QUESTION_COUNT` (=20), `MOCK_TIME_LIMIT_SECONDS` (=1500),
  `MOCK_PASS_CORRECT_B` (=18), `MAX_QUESTION_MEDIA_BYTES` (video cap), and image caps.
- Remove SAT-specific exam sizing vars and `DESMOS_API_KEY`.

## Migrations

- Fresh Alembic history for prava-bot's schema (this is a new DB, not a SATStudy migration
  chain). Any model change ships with a migration; `alembic upgrade head` must apply cleanly
  on startup (Docker) and in the pre-push gate.

## Deployment

- **New, separate** Railway service, **new bot token** (BotFather), **new Postgres DB** —
  fully independent from SATStudy.
- Same Dockerfile pattern (build Vite → serve from FastAPI → migrate → bind `PORT`).
- Seed script in `app/scripts/` to load the initial authored question bank.

## Testing

- `pytest` suites mirroring SATStudy: auth, onboarding/practice flow, mock-exam
  flow (fidelity: 20 q, 25-min timer, pass at 18), mistakes review, media
  upload/serve/validation (image/gif/video, oversize rejection, draft auth), admin gating,
  security hardening.
- Frontend Playwright e2e for the practice loop, media rendering, and the timed mock.
