# 09 — Security

A threat-model-style review with concrete controls, not a generic checklist. Baseline
protections are inherited from SATStudy; this spec makes the prava-bot-specific requirements
explicit and testable.

## Assets to protect

- Exam integrity (correct answers, pass/fail, timer, question set).
- User privacy (Telegram identity, study history).
- Content integrity (only authorized, verified content is published).
- Admin capability (no privilege escalation).

## Telegram authentication

- Validate Mini App **`initData`** on the server: recompute the HMAC with the bot token per
  Telegram's spec and `hmac.compare_digest` against the supplied hash. Reject on mismatch.
- Enforce **max age** (`TELEGRAM_INIT_DATA_MAX_AGE_SECONDS`); reject future-dated `auth_date`.
- **Never trust a client-supplied `user.id`** or any user field outside the signed `initData`.
  The authenticated identity comes only from validated `initData`.
- On success, create a **server session** (`user_id` only) signed with `SESSION_SECRET`
  (itsdangerous); the client never carries identity/role in a mutable token.
- **Replay**: `initData` is only accepted to *establish* a session; subsequent requests use
  the session cookie. Combined with max-age this bounds replay. (Optional hardening: cache
  recently seen `initData` hashes for the max-age window to reject exact replays.)
- **Session rotation**: rotate the session id on privilege-relevant transitions; provide
  **logout** that clears the session; a user removed from `ADMIN_TELEGRAM_IDS` loses admin
  capability on next request (role resolved server-side each time, not cached in the cookie).

## Authorization / IDOR

**Every** backend resource verifies ownership/role **server-side**; the object id in the URL
is never sufficient. Concretely, scope by `user_id` from the session for:

- practice sessions & answers; mock attempts, mock questions, mock answers, results;
- readiness; ranking self-view; profiles; content reports the user filed.

Media: published-question media is public (behind content-hash URL); **draft/unpublished**
media is admin-only. Admin resources require the appropriate `AdminRole`. Changing a UUID in a
request must never return another user's private attempt/history — covered by explicit IDOR
tests below.

## Admin security

- Admin capability = in `ADMIN_TELEGRAM_IDS` **and** a resolved `AdminRole`; **every** admin
  endpoint checks the role server-side. Hiding frontend routes is **not** a control.
- **Least privilege** via roles ([08-admin.md](08-admin.md)); destructive/global ops require
  `superadmin`.
- **Audit** every admin action (`AdminAuditEvent`): who/what/when/entity/version.
- **Destructive-action confirmation** in UI **and** an idempotency/confirm token server-side
  for delete/archive/bulk.
- Stricter **session expiration** and **rate limits** for admin scopes than for students.
- **Privilege escalation** defenses: role changes are `superadmin`-only and audited; a user
  cannot set their own `admin_role`; mass-assignment protection (below) prevents smuggling
  `admin_role`/`is_correct`/`role` via request bodies.
- Optional second-factor: for `superadmin` destructive ops, an explicit re-confirmation step
  (justified if the team is small and the blast radius large).

## Exam integrity (critical)

The mock API must **never** leak the answer during a live attempt.

- Live mock question payload returns **only**: `question_version_id`, prompt, media URL,
  option **ids + text + position**. It must **not** return `is_correct`, `explanation`,
  `short_explanation`, or rule text until the attempt is `completed`.
- **Option-id inference defense**: option ids must not encode correctness or ordering (use
  random UUIDs; do not sort correct-first; do not expose a stable "position 1 == answer"
  pattern). Correctness lives only server-side on `AnswerOption.is_correct`.
- **Grading is server-side** at submit/expiry; the client never computes or submits
  `is_correct`, `correct_count`, or `passed`. Those fields are ignored if present in a request
  (mass-assignment allowlist).
- **Timer**: `expires_at` is server-authoritative; remaining time = `expires_at - now`
  (server clock). No pause. Client cannot extend the deadline; a submit/sync after
  `expires_at` does not change already-final results. **Auto-submit** server-side at expiry.
- **Question set** is pinned at start (`MockQuestion` → immutable `question_version_id`); the
  client cannot swap question ids or inject others; answers referencing a `question_version_id`
  not in the attempt are rejected.
- **Duplicate submission**: unique `(mock_attempt_id, question_version_id)` on `MockAnswer`;
  submitting an already-completed attempt is idempotent/rejected.
- **Readiness/ranking** are recomputed server-side from stored facts; client-provided scores
  are ignored.

## XSS / content security

Admin-authored text is shown to users → stored-XSS risk.

- Treat all content as **plain text**; **no arbitrary HTML** from authors. Render via React
  text nodes (auto-escaped); never `dangerouslySetInnerHTML` for author content.
- If lightweight formatting is ever needed, use a **restricted Markdown** subset rendered to
  safe elements with sanitization — **not** raw HTML. (v1: plain text + the existing
  math/exponent inline rendering only, which does not inject HTML from author strings.)
- Sanitize/validate everywhere author text flows: prompts, option text, explanations, rule
  text/title, `alt_text`, supporting-source notes, **uploaded file names** (never reflect raw
  filenames; storage keys are random).
- **CSP**: `default-src 'self'`; `media-src 'self'` (+ object-storage host if distinct, exact
  match); `img-src 'self' data: <media host>`; `script-src 'self' https://telegram.org`;
  `frame-ancestors` Telegram; `object-src 'none'`; `base-uri 'self'`. **Reject SVG media**
  entirely in v1 (see below).

## Media upload security

Admin-only endpoint. For every upload:
- **Sniff type from bytes** (Pillow/container probe); never trust client `Content-Type` or
  extension; reject extension/content mismatch.
- **Reject SVG** in v1 (script vector); allow only `image/png|jpeg|webp` (→ re-encode WebP),
  `image/gif`, `video/mp4`, `video/webm`.
- Guard **decompression bombs** (`Image.MAX_IMAGE_PIXELS`), **GIF frame bombs** (max frames),
  max **dimensions**, max **file size**, max **video duration**; validate video container/codec
  and reject non-web-playable files (no server transcoding v1).
- **Storage keys are random/non-user-controlled** (no path traversal); object writes go to a
  private prefix; served via content-addressed URL or signed URL.
- Compute `content_hash`; media rows are immutable (replacement = new object + new question
  version).

## API security

- **CSRF**: state-changing requests are same-origin JSON with the session cookie
  `SameSite=Lax`; require `Content-Type: application/json` and reject cross-site form posts.
- **CORS**: allow only the app origin(s) and Telegram; credentials restricted accordingly.
- **Rate limiting** per scope (auth/write/admin/exam) reused from SATStudy; stricter on
  admin/import.
- **Request-size limits** (body + upload caps); **pagination** has server-max page sizes to
  prevent enumeration/DoS.
- **SQL injection**: SQLAlchemy parameterized queries only; no string-built SQL.
- **Mass assignment**: strict Pydantic input schemas; server ignores/rejects client-supplied
  `is_correct`, `correct_count`, `passed`, `admin_role`, `points`, `readiness`, ids not owned.
- **Error/debug leakage**: generic error bodies with a correlation id (reuse SATStudy handler);
  `APP_DEBUG=false` enforced outside development; no stack traces to clients.
- **Dependencies/secrets**: pinned deps; secrets only via env/secret manager; never logged.

## Privacy (data minimization)

Stored: Telegram id; username/first/last name + photo (as provided by Telegram); study
results (answers, mocks, mistakes, readiness, points); timezone; optional target exam date;
`display_name`/`ranking_name` + `show_on_ranking`.

- **Do not collect phone number** (no concrete v1 requirement).
- **Ranking name** is user-controlled; Telegram username is **not** shown publicly unless the
  user opts in ([10-ranking.md](10-ranking.md)).
- **Deletion**: a user can request account+data deletion (removes profile, answers, mocks,
  mistakes, points, reports; audit logs retain only non-PII actor ids where legally needed).
- **Retention/export**: document retention windows; provide a self data-export where relevant.
- Do not log sensitive payloads (initData, tokens).

## Webhook / bot

- Verify the **`X-Telegram-Bot-Api-Secret-Token`** with `compare_digest` (reuse SATStudy);
  reject spoofed webhook requests.
- **Bot token** only in env/secret manager; the webhook secret must differ from
  `SESSION_SECRET` (enforced in settings).
- **Replay/duplicate updates**: bot handlers are idempotent; the bot only launches the Mini
  App (no sensitive state changes via bot in v1).
- Do not log full update payloads.

## Object storage

- **Railway S3-compatible Storage Bucket** (production v1), **private**; no public "list".
  Published media is served via the app's content-addressed route
  `/api/media/{media_id}/{content_hash}` (stream) or a **short-lived presigned GET**; draft
  media requires admin auth. Published media is cacheable **behind the content-hash URL**.
- **Storage keys are server-generated** (never derived from client filenames); credentials are
  least-privilege (put/get on the app's prefix only). Accessed only through the `MediaStorage`
  adapter so provider migration (R2/S3) does not change domain code.
- **No object overwrite** for immutable media (new hash = new key); an **orphan-cleanup** job
  removes media rows/objects not referenced by any version after a grace period.

## Security tests (explicit)

pytest/e2e must cover:
- forged `initData` (bad HMAC) → 401; expired `initData` → 401; future `auth_date` → 401;
- IDOR: user B cannot read user A's mock attempt/result/practice/profile/report → 404;
- admin escalation: non-admin hitting admin endpoints → 403; author cannot publish if role
  disallows; user cannot set `admin_role` via body;
- **exam answer non-leak**: live mock payload contains no `is_correct`/`explanation`/rule;
  option ids reveal no ordering pattern;
- client cannot extend the timer; submit/sync after `expires_at` doesn't change results;
  auto-submit at expiry works;
- swapping/injecting a `question_version_id` not in the attempt → rejected;
- duplicate mock/practice submission handled;
- malicious upload rejected (SVG, wrong-type, oversize, decompression bomb, frame bomb);
- stored-XSS payload in prompt/option/explanation/rule/alt/filename renders inert;
- oversized request body rejected; pagination cap enforced; rate limits enforced.
