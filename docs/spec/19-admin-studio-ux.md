# 19 — Admin Studio UX & Structure

Goal: make the admin studio **well-structured, discoverable, and comfortable** so a content
admin can run the whole product (questions **and** the Theory catalogue) from the Mini App UI —
without shell scripts or raw API calls. This is primarily a **frontend restructure + wiring**
task, plus the **minimum backend list endpoints** needed to browse/edit non-published Theory
content.

## Current state (verified 2026-09-03)

- `frontend/src/admin.tsx` exposes only **4 flat tabs**: `Panel` (raw dashboard), `Savollar`
  (question list), `Yangi` (question editor), `Shikoyatlar` (reports); `QA` is hidden (reachable
  only from the list). Everything is question-centric.
- Backend already exposes (unused by the UI):
  - `/api/admin/theory/*` — full CRUD + review/publish for **sections, articles (block editor),
    signs, markings, gestures, lights**, plus `GET /api/admin/theory/review-queue` and
    `POST /verify/{entity}/{version_id}` (see `app/api/theory_admin_routes.py`).
  - `/api/admin/rules` (search/create/supersede), `/api/admin/import`, `/api/admin/duplicates/check`,
    `/api/admin/users/{id}/role`.
- **Gap 1 — no Theory management UI**: admins cannot create/edit/publish any Theory content from
  the studio; the whole `theory_admin` surface is unreachable in the UI.
- **Gap 2 — no admin *list* endpoints for Theory**: student readers (`/api/theory/*`) return
  **published-only**, so drafts/needs_review items can't be listed for editing. Only the
  review-queue surfaces pending items.
- **Gap 3 — no review-queue UI**: `review-queue` endpoint exists but nothing renders it.
- **Gap 4 — raw dashboard**: dumps a status→count dict and topic list with English keys; not
  readable.
- **Gap 5 — flat nav / weak affordances**: no grouping, no Uzbek topic labels, no status badges,
  QA hidden, no role-aware structure beyond the review buttons.

## Design principles

- **Reuse first**: wire existing endpoints and `theory_admin` shapes; do **not** duplicate
  business logic or invent parallel concepts. Add only the small **admin list** read endpoints
  that are genuinely missing (Gap 2), reusing the existing `theory` service list functions with
  an `include_unpublished` flag (admin/role-gated; students still get published-only).
- **Security unchanged**: server-side auth/role gating on every endpoint is the source of truth;
  the UI role-gate is convenience only. All authored content renders as **text nodes** (no raw
  HTML) per docs/spec/09. No answer leak anywhere a question is embedded.
- **Uzbek (Latin)** copy throughout; mobile-first but usable on desktop; consistent card styling
  and status badges.
- **No versioning-model change**: editing published content forks a new version (existing
  behaviour); publish repoints current version.

## Scope

A. **Grouped, role-aware navigation** replacing the 4 flat tabs. Proposed IA:
   - **Panel** (dashboard)
   - **Savollar** (questions: list + editor + QA as a coherent flow)
   - **Nazariya** (Theory management with sub-nav: Bo'limlar, Maqolalar, Belgilar, Chiziqlar,
     Ishoralar, Svetofor)
   - **Ko'rik navbati** (review queue: pending questions + theory versions with quick
     review/publish)
   - **Shikoyatlar** (reports)
   Role visibility: authors see content tabs; reviewer/admin/superadmin additionally see review
   actions and the review queue; role-management stays superadmin/admin only.

B. **Dashboard v2** — readable Uzbek labels for each status count, topic coverage as labelled
   bars (using the Uzbek topic map), and quick-link cards for "open reports" and "review queue"
   counts.

C. **Theory management UI (Nazariya)** — for **signs, markings, gestures, lights** at minimum
   (sections + articles if time allows): a list (including drafts via the new admin list
   endpoints), a create/edit form using the existing content-input fields, media
   attach (reuse `uploadMedia`), rule linking (reuse `RulePicker`), and the
   submit-review → review → publish transitions with status badges. A detail/preview mirrors the
   student card.

D. **Review-queue UI** — render `GET /api/admin/theory/review-queue` (+ question review states)
   grouped by entity type, each row linking to its editor and offering review/publish
   (role-gated).

E. **Comfort polish** — Uzbek `Topic` label map, status badges (draft/needs_review/reviewed/
   published/needs_reverification/superseded/archived), consistent `.admin` card layout, inline
   field help, non-blocking success/error toasts (can reuse the existing msg/err pattern),
   preserve the existing live preview.

F. **Minimum backend additions** — admin list endpoints under `/api/admin/theory/*`
   (e.g. `GET /signs?include_unpublished=true`, and equivalents for markings/gestures/lights/
   sections/articles) reusing `app/services/theory.py` list functions extended with an
   `include_unpublished: bool` flag (admin-gated route). No schema/migration change.

G. **Tests** — backend: new admin list endpoints are role-gated (401/403 for non-admin) and
   include drafts only for admins while student readers stay published-only; frontend `npm run
   build` passes (tsc typecheck of new `adminApi.theory*` methods + types).

## Non-goals
- No redesign of the student-facing Mini App tabs, exam mode, or theory reader.
- No new Theory features/entities; no schema/migration changes.
- Bulk-import UI, duplicates UI, and full article block-editor are **stretch** (nice-to-have; do
  only if they don't jeopardise the core scope) — otherwise track as follow-ups.

## Acceptance criteria (verifiable)
1. `python -m compileall app` clean; `python -m pytest -q` green incl. new tests for the admin
   list endpoints (role-gated; drafts admin-only; students published-only).
2. `cd frontend && npm run build` passes (tsc + vite) with the new nav, dashboard v2, Theory
   management UI, and review-queue UI wired via typed `adminApi` methods.
3. Navigation is grouped and role-aware (authors vs reviewer/admin), Uzbek labels, status badges;
   QA reachable within the Savollar flow.
4. From the UI an admin can list (incl. drafts), create, edit, and publish at least signs,
   markings, gestures, and lights; and see the review queue.
5. Deployed to `main` (Railway); live smoke: `/health` 200, an admin theory list endpoint returns
   drafts for an admin and 403 for a non-admin, and the built admin bundle loads.

## Round-robin workflow (OPO)
1. **system_architect** turns this brief into a concrete plan: component tree for `admin.tsx`,
   exact new `adminApi.theory*` methods + `types.ts` additions, the exact new backend list
   endpoints + service signature changes, and a phased checklist mapped to the acceptance
   criteria. Output is the implementation contract.
2. **backend_developer** implements per that plan; runs the local gate; no deploy.
3. **tester** + **system_architect** + **backend_developer (fresh-eyes)** review; each returns
   `VERDICT: APPROVE|REJECT` with file:line. Iterate until all APPROVE.
4. OPO runs the pre-push gate, deploys, verifies live.
