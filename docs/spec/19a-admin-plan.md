# 19a — Admin Studio: Implementation Contract (DESIGN)

Concrete, implementable plan derived from `docs/spec/19-admin-studio-ux.md`.
**No app code is written in this stage** — this is the contract the `backend_developer`
and frontend implementer follow. Verified against the real tree on 2026-09-03.

Guiding constraints (from spec-19):
- **Reuse first**; add only the missing admin *list* read endpoints (Gap 2).
- **Server-side role gating is the source of truth** (`app/api/admin_deps.py::require_role`);
  the UI role-gate is convenience only.
- **No schema/migration change.** No new Theory features/entities.
- All authored content renders as **React text nodes** (no `dangerouslySetInnerHTML`).
- Uzbek (Latin) copy throughout; reuse `frontend/src/i18n/uz.ts` (`uz`, `TOPIC_LABELS`, `topicLabel`).

---

## 1. Admin Information Architecture

### 1.1 Grouped, role-aware navigation (replaces the 4 flat tabs)

Top-level groups rendered in `AdminArea` (`frontend/src/admin.tsx`):

| Group (Uzbek)     | Internal id  | Min role to see        | Contents |
|-------------------|--------------|------------------------|----------|
| **Panel**         | `dashboard`  | content_author         | Dashboard v2 |
| **Savollar**      | `questions`  | content_author         | Question list → editor → QA (one coherent flow) |
| **Nazariya**      | `theory`     | content_author         | Sub-nav: Bo'limlar / Maqolalar / Belgilar / Chiziqlar / Ishoralar / Svetofor |
| **Ko'rik navbati**| `review`     | content_reviewer       | Review queue (theory versions + pending questions) |
| **Shikoyatlar**   | `reports`    | content_author*        | Reports queue (existing) |

Role gating in the UI (mirrors server ranks in `app/domain/enums.py`: author=1,
reviewer=2, admin=3, superadmin=4):
- `canReview = role ∈ {content_reviewer, admin, superadmin}` (already computed).
- **Ko'rik navbati** tab is only rendered when `canReview` (the endpoint is `ReviewerUser`-gated anyway → 403 otherwise).
- Review/publish action buttons in every editor stay gated by `canReview` (existing pattern).
- Role management stays in the existing admin_routes surface (superadmin/admin only) — out of scope here.

Nav is a two-row control: primary group buttons (existing `.admin-nav` styling), and — when
`theory` is active — a secondary sub-nav row (`.admin-subnav`, new style, mirror `.admin-nav`).

### 1.2 React component tree for `admin.tsx`

```
AdminArea({ role, onExit })
├─ state: group: AdminGroup, theorySub: TheoryEntity, editing refs per entity
├─ <nav .admin-nav>            // primary groups (role-filtered)
├─ Panel  → <Dashboard/>                        (rewritten → Dashboard v2)
├─ Savollar → <QuestionsSection/>               (wraps existing QuestionList/Editor/QaPanel flow)
│     ├─ <QuestionList onEdit onQa/>            (EXISTING, unchanged)
│     ├─ <Editor .../>                          (EXISTING, unchanged)
│     └─ <QaPanel questionId/>                  (EXISTING, unchanged)
├─ Nazariya → <TheorySection/>                  (NEW)
│     ├─ <nav .admin-subnav>  // Bo'limlar…Svetofor
│     └─ per entity:
│        <TheoryList  entity onCreate onEdit/>  (NEW, generic list; drafts via new endpoints)
│        <TheoryEditor entity id? canReview onSaved/>  (NEW, generic create/edit + transitions)
│              ├─ entity-specific field set (see §3.3 field maps)
│              ├─ <RulePicker/>                 (EXISTING — reused for rule_codes)
│              ├─ media <input type=file> → adminApi.uploadMedia (EXISTING helper)
│              └─ <TheoryPreview entity data/>  (NEW — mirrors student card, text nodes only)
├─ Ko'rik navbati → <ReviewQueue canReview onOpen/>  (NEW)
│     └─ rows grouped by type → deep-link into <TheoryEditor entity id> or Editor
└─ Shikoyatlar → <ReportsQueue/>                (EXISTING, unchanged)
```

Shared patterns reused verbatim:
- `msg`/`err` `useState<string|null>` + inline `<p className="explain">` (no new toast lib).
- `RulePicker` (rule_codes chips), `LivePreview`/`TheoryPreview` (right column of `editor-layout`).
- `adminApi.uploadMedia(file)` → sets `media_id` on the entity draft.
- Status badge component (NEW small `<StatusBadge status/>`, see §4.3).

New generic types local to admin.tsx:
```ts
type AdminGroup = "dashboard" | "questions" | "theory" | "review" | "reports";
type TheoryEntity = "sections" | "articles" | "signs" | "markings" | "gestures" | "lights";
```

`TheoryEditor` is **generic over entity** with an entity→config table (create endpoint,
edit endpoint, transition endpoints, field descriptors). This avoids 6 near-duplicate editors.
Sections + articles editors are the **stretch** items (§5); signs/markings/gestures/lights are core.

---

## 2. NEW backend admin list endpoints

All added to the **existing** router in `app/api/theory_admin_routes.py`
(`prefix="/api/admin/theory"`), gated by `AuthorUser` (min role `CONTENT_AUTHOR`) — the same
gate already used for create/edit. `include_unpublished` defaults to **false** so even the admin
route is explicit; students keep using `/api/theory/*` which never exposes the flag.

### 2.1 Service signature changes — `app/services/theory.py`

Add an `include_unpublished: bool = False` keyword-only flag. When **False**, behaviour is
**byte-for-byte identical** to today (filter `lifecycle_status == PUBLISHED`). When **True**,
drop the status filter and resolve display fields from `current_version_id` **or** the latest
version row (drafts have `current_version_id is None`).

New private helper (add near the other `_*` helpers in `theory.py`):
```python
def _latest_version_id(db, version_model, fk_attr: str, container_id: str) -> str | None:
    """current_version_id if published, else the highest-version row for this container."""
    return db.scalar(
        select(version_model.id)
        .where(getattr(version_model, fk_attr) == container_id)
        .order_by(version_model.version.desc())
        .limit(1)
    )
```

Exact signature changes (keyword-only flag; existing callers unaffected):
```python
def list_sections(db, *, user=None, include_unpublished: bool = False) -> list[dict]: ...
def list_signs(db, *, family=None, include_unpublished: bool = False) -> list[dict]: ...
def list_markings(db, *, include_unpublished: bool = False) -> list[dict]: ...
def list_gestures(db, *, include_unpublished: bool = False) -> list[dict]: ...
def list_lights(db, *, include_unpublished: bool = False) -> list[dict]: ...
# NEW function (no student equivalent exists as a flat list):
def list_articles(db, *, section_id: str | None = None,
                  include_unpublished: bool = False) -> list[dict]: ...
```

Implementation notes per function:
- Build the base `select(Model)`; **only** append `.where(Model.lifecycle_status == PUBLISHED)`
  when `not include_unpublished`.
- Card builders (`_sign_card`, inline builders in `list_markings/gestures/lights`, `_section_out`,
  `_article_card`) currently read the translation via `current_version_id`. For unpublished rows
  resolve `vid = row.current_version_id or _latest_version_id(db, <VersionModel>, "<fk>", row.id)`
  and read the translation from `vid`. Add `"lifecycle_status": row.lifecycle_status.value` and
  `"current_version_id": row.current_version_id` and `"latest_version_id": vid` to the dict when
  `include_unpublished` (harmless extra keys; students never see this path).
- `list_articles`: mirror `get_section`'s article query but optional `section_id` and status
  filter; return `_article_card`-shaped dicts (+ the 3 admin keys). `_article_card` already reads
  from `current_version_id`; extend it to accept a resolved `version_id` fallback.

**Security invariant to test:** with `include_unpublished` omitted/False the three student list
endpoints (`/api/theory/signs|markings|...`) return the identical published-only set — assert a
draft row is absent.

### 2.2 New routes (append to `theory_admin_routes.py`)

```python
from fastapi import Query
from app.services import theory as theory_service

@router.get("/sections")
def admin_list_sections(user: AuthorUser, db: DbSession,
                        include_unpublished: bool = Query(default=True)) -> dict:
    return {"sections": theory_service.list_sections(db, include_unpublished=include_unpublished)}

@router.get("/articles")
def admin_list_articles(user: AuthorUser, db: DbSession,
                        section_id: str | None = Query(default=None),
                        include_unpublished: bool = Query(default=True)) -> dict:
    return {"articles": theory_service.list_articles(
        db, section_id=section_id, include_unpublished=include_unpublished)}

@router.get("/signs")
def admin_list_signs(user: AuthorUser, db: DbSession,
                     family: str | None = Query(default=None),
                     include_unpublished: bool = Query(default=True)) -> dict:
    return {"signs": theory_service.list_signs(db, family=family,
                                               include_unpublished=include_unpublished)}

@router.get("/markings")
def admin_list_markings(user: AuthorUser, db: DbSession,
                        include_unpublished: bool = Query(default=True)) -> dict:
    return {"markings": theory_service.list_markings(db, include_unpublished=include_unpublished)}

@router.get("/gestures")
def admin_list_gestures(user: AuthorUser, db: DbSession,
                        include_unpublished: bool = Query(default=True)) -> dict:
    return {"gestures": theory_service.list_gestures(db, include_unpublished=include_unpublished)}

@router.get("/lights")
def admin_list_lights(user: AuthorUser, db: DbSession,
                      include_unpublished: bool = Query(default=True)) -> dict:
    return {"lights": theory_service.list_lights(db, include_unpublished=include_unpublished)}
```

> Route-ordering caution: these static paths (`/signs`, `/markings`, …) live on the same router
> as existing `POST /signs` etc. GET vs POST disambiguates; no path collision with the
> `/{id}` mutation routes because those are on distinct verbs/paths. Register order unchanged.

### 2.3 Response shapes

`GET /api/admin/theory/signs` (others analogous):
```jsonc
{ "signs": [
  { "id": "…", "code": "1.1", "family": "warning", "name": "…",
    "media_url": "…|null",
    "lifecycle_status": "draft|needs_review|reviewed|published|needs_reverification|superseded|archived",
    "current_version_id": "…|null", "latest_version_id": "…|null" }
]}
```
- markings: adds `code`, `group`; sections: `slug`,`topic`,`title`,`subtitle`,`article_count`;
  articles: `slug`,`kind`,`title`,`summary`,`section_id`; gestures: `code`,`animation_url`;
  lights: `kind`,`title`. Each carries the 3 admin keys (`lifecycle_status`,
  `current_version_id`, `latest_version_id`).
- Non-admin (no effective role) → **403** (`require_role` raises). Unauthenticated → **401** (`CurrentUser`).

---

## 3. NEW frontend `adminApi.theory*` methods + `types.ts` additions

### 3.1 `types.ts` — admin list item types (extend student cards with lifecycle)

```ts
export interface AdminLifecycleFields {
  lifecycle_status: string;
  current_version_id: string | null;
  latest_version_id: string | null;
}
export type AdminSignListItem    = SignCard    & AdminLifecycleFields;
export type AdminMarkingListItem = MarkingCard & AdminLifecycleFields;
export type AdminGestureListItem = GestureCard & AdminLifecycleFields;
export type AdminLightListItem   = LightCard   & AdminLifecycleFields;
export type AdminSectionListItem = TheorySectionCard & AdminLifecycleFields;
export type AdminArticleListItem = TheoryArticleCard & AdminLifecycleFields & { section_id: string };
```

### 3.2 `types.ts` — content-input types (mirror `app/api/theory_schemas.py`)

```ts
export interface SignCreateInput { official_code: string; family: string; media_id?: string | null; position?: number; }
export interface SignContentInput {
  name: string; meaning: string; driver_action: string;
  important?: string | null; exam_trap?: string | null; memory_tip?: string | null;
  keywords?: string | null; media_id?: string | null; ai_assisted?: boolean;
  rule_codes: string[]; question_ids?: string[];
}
export interface MarkingCreateInput { group: string; code?: string | null; media_id?: string | null; position?: number; }
export interface MarkingContentInput {
  name: string; meaning: string; can_cross?: string | null; can_stop_park?: string | null;
  conflict_rule?: string | null; exam_trap?: string | null; memory_tip?: string | null;
  keywords?: string | null; media_id?: string | null; ai_assisted?: boolean; rule_codes: string[];
}
export interface GestureCreateInput { code?: string | null; media_id?: string | null; animation_media_id?: string | null; position?: number; }
export interface GestureContentInput {
  name: string; position_desc: string; allowed: string; forbidden: string;
  memory_tip?: string | null; keywords?: string | null; media_id?: string | null;
  animation_media_id?: string | null; ai_assisted?: boolean; rule_codes: string[];
}
export interface LightCreateInput { kind: string; media_id?: string | null; position?: number; }
export interface LightContentInput {
  title: string; meaning: string; movement_permitted?: string | null; direction_permitted?: string | null;
  exceptions?: string | null; typical_exam_situation?: string | null; keywords?: string | null;
  media_id?: string | null; ai_assisted?: boolean; rule_codes: string[];
}
export interface SectionCreateInput { slug: string; title: string; subtitle?: string; topic?: string | null; position?: number; icon_media_id?: string | null; }
export interface ArticleCreateInput { section_id: string; slug: string; kind?: string; position?: number; }
// (ArticleContentInput / BlockInput are STRETCH — mirror BlockIn/ArticleContentIn when built.)

export interface TheoryVersionOut {           // shape of _version_out(...)
  id: string; version: number; status: string;
  authored_by_user_id: string | null; reviewed_by_user_id: string | null;
  approved_by_user_id: string | null; verified_at: string | null;
}
// create responses also include the container id key, e.g. { road_sign_id, ...TheoryVersionOut }
export type SignCreateOut    = TheoryVersionOut & { road_sign_id: string };
export type MarkingCreateOut = TheoryVersionOut & { road_marking_id: string };
export type GestureCreateOut = TheoryVersionOut & { gesture_id: string };
export type LightCreateOut   = TheoryVersionOut & { light_id: string };

export interface ReviewQueueOut {
  articles: ReviewQueueRow[]; signs: ReviewQueueRow[]; markings: ReviewQueueRow[];
  gestures: ReviewQueueRow[]; lights: ReviewQueueRow[];
}
export interface ReviewQueueRow { version_id: string; container_id: string; version: number; status: string; }
```

### 3.3 `api.ts` — new methods on `adminApi` (all paths verified against routes)

Read (NEW list endpoints, §2.2):
| method | path |
|---|---|
| `theoryListSections(includeUnpublished=true)` | `GET /api/admin/theory/sections?include_unpublished=` |
| `theoryListArticles(sectionId?, includeUnpublished=true)` | `GET /api/admin/theory/articles?section_id=&include_unpublished=` |
| `theoryListSigns(family?, includeUnpublished=true)` | `GET /api/admin/theory/signs?family=&include_unpublished=` |
| `theoryListMarkings(includeUnpublished=true)` | `GET /api/admin/theory/markings?include_unpublished=` |
| `theoryListGestures(includeUnpublished=true)` | `GET /api/admin/theory/gestures?include_unpublished=` |
| `theoryListLights(includeUnpublished=true)` | `GET /api/admin/theory/lights?include_unpublished=` |

Write/transition (reuse EXISTING routes in `theory_admin_routes.py`):
| method | verb path | req type → res type |
|---|---|---|
| `theoryCreateSign(p)` | `POST /api/admin/theory/signs` | `SignCreateInput` → `SignCreateOut` |
| `theoryEditSign(id,p)` | `PUT /api/admin/theory/signs/{id}` | `SignContentInput` → `{road_sign_id,...TheoryVersionOut}` |
| `theorySubmitSign(vid)` | `POST /api/admin/theory/sign-versions/{vid}/submit-review` | `{}` → `TheoryVersionOut` |
| `theoryReviewSign(vid)` | `POST /api/admin/theory/sign-versions/{vid}/review` | `{}` → `TheoryVersionOut` |
| `theoryPublishSign(vid)` | `POST /api/admin/theory/sign-versions/{vid}/publish` | `{}` → `TheoryVersionOut` |
| …markings | `POST /markings`, `PUT /markings/{id}`, `POST /marking-versions/{vid}/{submit-review|review|publish}` | analogous |
| …gestures | `POST /gestures`, `PUT /gestures/{id}`, `POST /gesture-versions/{vid}/…` | analogous |
| …lights | `POST /lights`, `PUT /lights/{id}`, `POST /light-versions/{vid}/…` | analogous |
| …sections (STRETCH) | `POST /sections`, `PUT /sections/{id}/translation`, `POST /sections/{id}/publish` | analogous |
| …articles (STRETCH) | `POST /articles`, `PUT /articles/{id}`, `POST /article-versions/{vid}/…` | analogous |
| `theoryReviewQueue()` | `GET /api/admin/theory/review-queue` | → `ReviewQueueOut` |
| `theoryDetailSign(code)` etc. | reuse existing `theoryApi.sign()`… for the **preview** of published items; drafts preview from local editor state | |

Reference implementation for one method (follow the existing `request<T>` + `import("./types")` idiom):
```ts
theoryListSigns: (family?: string, includeUnpublished = true) => {
  const p = new URLSearchParams();
  if (family) p.set("family", family);
  p.set("include_unpublished", String(includeUnpublished));
  return request<{ signs: import("./types").AdminSignListItem[] }>(
    `/api/admin/theory/signs?${p.toString()}`);
},
theoryCreateSign: (payload: import("./types").SignCreateInput) =>
  request<import("./types").SignCreateOut>("/api/admin/theory/signs",
    { method: "POST", body: JSON.stringify(payload) }),
theoryEditSign: (id: string, payload: import("./types").SignContentInput) =>
  request<import("./types").TheoryVersionOut & { road_sign_id: string }>(
    `/api/admin/theory/signs/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
theorySubmitSign: (vid: string) =>
  request<import("./types").TheoryVersionOut>(
    `/api/admin/theory/sign-versions/${vid}/submit-review`, { method: "POST", body: "{}" }),
```

Entity→field descriptor map (drives the generic `TheoryEditor`; each field is
`{ key, label(uz), type: "text"|"textarea"|"select", options? }`):
- **signs**: create `official_code`,`family(select)`; content `name`,`meaning`,`driver_action`,
  `important`,`exam_trap`,`memory_tip`,`keywords`,`media`,`rule_codes(RulePicker)`.
- **markings**: create `group(select)`,`code`; content `name`,`meaning`,`can_cross`,
  `can_stop_park`,`conflict_rule`,`exam_trap`,`memory_tip`,`keywords`,`media`,`rule_codes`.
- **gestures**: create `code`; content `name`,`position_desc`,`allowed`,`forbidden`,
  `memory_tip`,`keywords`,`media`,`animation_media`,`rule_codes`.
- **lights**: create `kind(select)`; content `title`,`meaning`,`movement_permitted`,
  `direction_permitted`,`exceptions`,`typical_exam_situation`,`keywords`,`media`,`rule_codes`.

Select option enums (must match `theory_schemas.py` Literals):
- sign family: warning, priority, prohibitory, mandatory, information, service, additional_plate
- marking group: horizontal, vertical, temporary
- light kind: main, arrow_section, flashing, pedestrian, railway, special
- article kind: lesson, reference, quick_ref, common_mistake

---

## 4. Dashboard v2 + label maps + status badges

### 4.1 Layout (rewrite `Dashboard()` in `admin.tsx`; data from existing `adminApi.overview()`)

Row 1 — **status count cards** (`data.counts`), each label via `STATUS_LABELS` (§4.2), value large.
Row 2 — **quick-link cards**: "Ochiq shikoyatlar: N" → jumps to Shikoyatlar; "Ko'rik navbati" →
count = sum of review-queue rows (call `adminApi.theoryReviewQueue()` for the badge) → jumps to
Ko'rik navbati; "Media: N obyekt / X MB" (from `data.media_storage`).
Row 3 — **Mavzu qamrovi** (topic coverage) as labelled horizontal bars: for each
`data.topic_coverage` entry render `topicLabel(topic)` + a bar whose width = share of max, with
the count at the end. Reuse `.admin-grid`/`.admin-stat`; add `.admin-bar`/`.admin-bar-fill`.
Row 4 (optional) — `questions_without_media_where_likely_needed`: list count + expandable ids.

No new endpoint required; all fields already exist on `AdminOverview`.

### 4.2 Uzbek Topic label map — REUSE existing
Use `TOPIC_LABELS` / `topicLabel(topic)` from `frontend/src/i18n/uz.ts` (already complete for all
15 topics). **Delete** the local raw `TOPICS` array in `admin.tsx` and the raw-key `<option>`s in
`Editor` — replace with `Object.keys(TOPIC_LABELS)` + `topicLabel`.

### 4.3 Status label map + badge set (NEW in `admin.tsx` or `uz.ts`)
```ts
export const STATUS_LABELS: Record<string,string> = {
  draft: "Qoralama",
  needs_review: "Ko'rik kutilmoqda",
  reviewed: "Ko'rildi",
  published: "Nashr etilgan",
  needs_reverification: "Qayta tekshirish kerak",
  superseded: "Eskirgan",
  archived: "Arxivlangan",
};
```
`<StatusBadge status/>` → `<span className={"badge badge-"+status}>{STATUS_LABELS[status]||status}</span>`.
Badge colors (add to `styles.css`): draft=grey, needs_review=amber, reviewed=blue,
published=green, needs_reverification=orange, superseded=muted-strikethrough, archived=dark-grey.
Report statuses (open/triaged/resolved/rejected) keep the existing Shikoyatlar copy.

---

## 5. Phased checklist mapped 1:1 to spec-19 acceptance criteria

**Phase B1 — Backend list endpoints (AC #1, #4, #5)**
- [ ] Add `_latest_version_id` helper + `include_unpublished` flag to `list_sections/list_signs/
      list_markings/list_gestures/list_lights`; add `list_articles`. Card builders resolve draft
      version + emit `lifecycle_status`/`current_version_id`/`latest_version_id`.
- [ ] Add 6 GET routes to `theory_admin_routes.py` (`AuthorUser`-gated).
- [ ] Tests (`tests/test_theory*` / new `tests/test_admin_theory_list.py`):
      403 for non-admin, 401 unauth; admin sees a seeded **draft**; student `/api/theory/*`
      still excludes it (published-only unchanged). → satisfies **AC #1**.

**Phase F1 — Nav + Dashboard v2 (AC #3)**
- [ ] Replace flat tabs with grouped role-aware nav + Nazariya sub-nav; QA reachable inside Savollar.
- [ ] `STATUS_LABELS` + `<StatusBadge>`; reuse `TOPIC_LABELS`/`topicLabel`; drop local `TOPICS`.
- [ ] Dashboard v2 (status cards, quick-links, labelled coverage bars). → **AC #3**.

**Phase F2 — Theory management UI core (AC #4, #2)**
- [ ] `types.ts` additions (§3.1–3.2); `adminApi.theory*` methods (§3.3).
- [ ] Generic `<TheoryList>` (drafts via new endpoints, status badges) for signs/markings/
      gestures/lights.
- [ ] Generic `<TheoryEditor>` create+edit+transitions, reusing `RulePicker`, `uploadMedia`,
      `msg`/`err`; `<TheoryPreview>` mirrors the student card (text nodes only).
- [ ] `npm run build` (tsc+vite) green. → **AC #2, AC #4** (list incl. drafts, create, edit, publish).

**Phase F3 — Review-queue UI (AC #4)**
- [ ] `<ReviewQueue>` renders `theoryReviewQueue()` grouped by entity; each row deep-links to its
      editor with review/publish (role-gated). → **AC #4** (see the review queue).

**Phase V — Verify/deploy (AC #5)**
- [ ] `python -m compileall app` clean; `python -m pytest -q` green; `npm run build` passes.
- [ ] Deploy `main` (Railway); smoke: `/health` 200; admin theory list returns drafts for admin &
      403 for non-admin; admin bundle loads. → **AC #5**.

**STRETCH (do only if core is safe; else follow-up):**
- [ ] Sections editor (create/translation/publish) + Articles list/editor.
- [ ] Article **block editor** (`BlockInput[]` — text/rule_callout/image/warning/memory_tip/…).
- [ ] Bulk-import UI (`/api/admin/import`), duplicates UI (`/api/admin/duplicates/check`).

---

## HANDOFF SUMMARY (developer follows this order)

1. **Backend first (Phase B1):** in `app/services/theory.py` add `_latest_version_id` + a
   keyword-only `include_unpublished: bool = False` to `list_sections/list_signs/list_markings/
   list_gestures/list_lights`, and add `list_articles(...)`. Only drop the `== PUBLISHED` filter
   when the flag is true; resolve draft display text via `current_version_id or latest`. Emit the
   3 admin keys. Then add the 6 `AuthorUser`-gated GET routes to `app/api/theory_admin_routes.py`
   (§2.2). Do **not** touch `/api/theory/*` (students stay published-only). No schema changes.
2. **Test the invariant:** non-admin→403/401; admin sees drafts; students don't. Run
   `python -m compileall app` and `python -m pytest -q`.
3. **Frontend types+api:** add the types in §3.1–3.2 and the `adminApi.theory*` methods in §3.3
   to `frontend/src/api.ts` / `types.ts` (keep the `request<T>` + `import("./types")` idiom).
4. **Frontend UI:** rewrite `admin.tsx` nav to grouped/role-aware (§1), Dashboard v2 (§4),
   generic `<TheoryList>/<TheoryEditor>/<TheoryPreview>` for signs/markings/gestures/lights (§1.2,
   §3.3 field map), and `<ReviewQueue>` (§3.3). Reuse `RulePicker`, `uploadMedia`, `msg`/`err`,
   `TOPIC_LABELS`. Add `STATUS_LABELS` + `<StatusBadge>` and badge CSS.
5. **Gate:** `cd frontend && npm run build` must pass (tsc+vite). Sections/articles editor,
   article block editor, and bulk-import UI are **stretch** — ship core (signs/markings/gestures/
   lights + review queue + dashboard) first.
6. **Non-negotiables:** server-side role gating is the source of truth; render authored content as
   text nodes only (no `dangerouslySetInnerHTML`); no answer leak in any preview; no schema/
   migration change; Uzbek (Latin) copy throughout.
