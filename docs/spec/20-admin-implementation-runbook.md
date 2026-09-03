# 20 - Admin implementation runbook

This document is the **normative execution order** for implementing the Admin Studio described in [19-admin-studio-mobile-first.md](19-admin-studio-mobile-first.md).

The implementation agent must follow this document **phase by phase in the exact order below**. Do not redesign the product while implementing it. Do not replace decisions in this file with alternatives that seem cleaner. If this file conflicts with softer wording such as "suggested", "preferred", "may", or "recommended" in spec 19, **this file wins**.

The goal is to remove product/architecture decisions from the implementation task. The agent's job is to implement, test, and fix.

## 0. Execution rules

1. Work on the current `main` branch unless the caller explicitly requests another branch.
2. Read specs `08`, `09`, `14`, `16`, `18`, `19`, and this file before changing code.
3. Preserve all existing learner functionality while refactoring Admin.
4. Do not change `ExamConfig` through Admin.
5. Do not reintroduce `MockTemplate` or a separate official-exam question bank.
6. Do not create a second frontend app. Admin remains inside the same React/Vite Telegram Mini App.
7. Do not add React Router. Use the exact Admin route-stack model defined below.
8. Do not add a second design system. Reuse `frontend/src/ui/tokens.css` and shared primitives.
9. Do not hard-delete published/versioned content that historical attempts may reference.
10. Every Admin mutation remains server-authorized and audited.
11. Finish the acceptance gate at the end of a phase before starting the next phase.
12. If an existing endpoint/component already satisfies the required contract, reuse it instead of duplicating it.
13. If an endpoint is missing, add exactly the endpoint described here.
14. If database migration head is still `0005`, use `0006_admin_assessments.py`. If another migration has landed first, use the next sequential number but implement exactly the schema in Phase 7.

## 1. Locked Admin information architecture

Use these exact five primary destinations:

```text
Panel
Savollar
Testlar
Nazariya
Ko'proq
```

Use these exact top-level route keys:

```ts
type AdminTab = "dashboard" | "questions" | "assessments" | "theory" | "more";
```

Use this route union for nested Admin navigation:

```ts
type AdminRoute =
  | { kind: "tab"; tab: AdminTab }
  | { kind: "question"; id: string }
  | { kind: "question-new" }
  | { kind: "question-preview"; id: string }
  | { kind: "question-qa"; id: string }
  | { kind: "assessment"; id: string }
  | { kind: "assessment-new" }
  | { kind: "theory-hub" }
  | { kind: "theory-section"; id: string }
  | { kind: "theory-article"; id: string }
  | { kind: "theory-article-new" }
  | { kind: "sign"; id: string }
  | { kind: "sign-new" }
  | { kind: "marking"; id: string }
  | { kind: "marking-new" }
  | { kind: "gesture"; id: string }
  | { kind: "gesture-new" }
  | { kind: "light"; id: string }
  | { kind: "light-new" }
  | { kind: "admin-search" }
  | { kind: "review" }
  | { kind: "reports" }
  | { kind: "rules" }
  | { kind: "rule"; id: string }
  | { kind: "media" }
  | { kind: "admins" }
  | { kind: "audit" }
  | { kind: "imports" };
```

Maintain:

```ts
const [routeStack, setRouteStack] = useState<AdminRoute[]>([
  { kind: "tab", tab: "dashboard" }
]);
```

Rules:

- bottom-nav tap resets `routeStack` to exactly one `{kind:"tab"}` route;
- opening detail pushes one route;
- Telegram BackButton pops one route;
- when there is only one root route, BackButton calls `onExit()` and returns to Profile;
- editor unsaved-change guard executes before pop/exit;
- consumer bottom navigation is never visible while Admin is open.

## 2. Locked frontend file structure

Refactor the current monolithic `frontend/src/admin.tsx` into exactly this structure:

```text
frontend/src/admin.tsx                  # compatibility barrel only; exports AdminArea
frontend/src/admin/
  AdminArea.tsx
  AdminShell.tsx
  AdminTopBar.tsx
  AdminBottomNav.tsx
  QuickCreateSheet.tsx
  AdminSearch.tsx
  admin.css
  routes.ts
  useAdminNavigation.ts

  dashboard/
    AdminDashboard.tsx

  questions/
    QuestionHub.tsx
    QuestionCard.tsx
    QuestionFiltersSheet.tsx
    QuestionEditor.tsx
    QuestionOptionsEditor.tsx
    QuestionPreview.tsx
    QuestionQA.tsx

  assessments/
    AssessmentHub.tsx
    AssessmentEditor.tsx
    AssessmentQuestionSelector.tsx
    AssessmentPreview.tsx

  theory/
    TheoryHub.tsx
    SectionsManager.tsx
    ArticlesManager.tsx
    ArticleEditor.tsx
    BlockEditor.tsx
    SignEditor.tsx
    MarkingEditor.tsx
    GestureEditor.tsx
    LightEditor.tsx

  rules/
    RulesManager.tsx
    RuleEditor.tsx

  media/
    MediaLibrary.tsx
    MediaPicker.tsx

  operations/
    MoreHub.tsx
    ReviewQueue.tsx
    Reports.tsx
    ImportExport.tsx
    AdminUsers.tsx
    AuditLog.tsx
```

Do not leave a second implementation of the same Admin screen in the old `admin.tsx`.

`frontend/src/admin.tsx` after refactor should only re-export the actual root component, for example:

```ts
export { AdminArea } from "./admin/AdminArea";
```

Keep shared primitives in `frontend/src/ui/`. Admin-specific composed components stay under `frontend/src/admin/`.

## 3. Locked responsive layout

Use one breakpoint for the major Admin navigation change:

```text
mobile/tablet: width < 768px
wide Admin:   width >= 768px
```

### Width < 768 px

Use:

- one-column content;
- Admin top bar;
- five-item Admin bottom navigation;
- floating quick-create button;
- editor preview as a separate sheet/screen;
- sticky editor action bar;
- card lists, never data tables;
- filter bottom sheets;
- no page-level horizontal scrolling.

### Width >= 768 px

Use:

- left Admin sidebar containing the same five destinations;
- no Admin bottom navigation;
- quick-create button in top bar instead of floating button;
- Admin workspace maximum width `1280px`;
- list/table views where useful;
- editor and preview side-by-side with editor taking `minmax(0, 1fr)` and preview `360px`;
- filters may be persistent beside lists.

The consumer `.ui-app { max-width: 640px }` must not constrain Admin at `>=768px`. Add an Admin-specific wrapper that becomes `max-width:1280px; width:100%`.

### Required mobile dimensions

All Admin screens must be manually/automatically checked at:

```text
320x640
360x740
390x844
430x932
```

No horizontal page overflow is permitted at any of those widths.

### Touch/input requirements

- minimum touch target: `44px`;
- minimum mobile text-input font-size: `16px`;
- floating quick-create button: `56x56px`;
- Admin bottom-nav item min-height: `64px` before safe-bottom padding;
- top bar min-height: `52px` plus safe-top padding;
- sticky editor action bar min-height: `60px` plus safe-bottom/nav accommodation.

## 4. Phase 1 - Admin shell and navigation

### Files to create/change

Create:

```text
frontend/src/admin/AdminArea.tsx
frontend/src/admin/AdminShell.tsx
frontend/src/admin/AdminTopBar.tsx
frontend/src/admin/AdminBottomNav.tsx
frontend/src/admin/QuickCreateSheet.tsx
frontend/src/admin/routes.ts
frontend/src/admin/useAdminNavigation.ts
frontend/src/admin/admin.css
```

Change:

```text
frontend/src/admin.tsx
frontend/src/main.tsx
frontend/src/telegram.ts
frontend/src/ui/components.tsx    # only if shared icon/primitives are missing
```

### Exact mobile shell order

Render in this order:

```text
AdminTopBar
Admin page content
QuickCreateButton
AdminBottomNav
```

`AdminBottomNav` items are exactly:

```text
Panel | Savollar | Testlar | Nazariya | Ko'proq
```

`QuickCreateButton` opens `QuickCreateSheet` containing exactly:

```text
Savol
Test
Nazariya maqolasi
Yo'l belgisi
Yo'l chizig'i
Regulirovshchik ishorasi
Svetofor holati
Qoida
```

Hide unauthorized items according to role.

### Phase 1 gate

Do not continue until:

- Admin opens from Profile;
- consumer nav disappears;
- five Admin destinations fit at 320 px;
- Telegram BackButton closes Admin only from Admin root and otherwise pops one Admin route;
- no current Admin feature is lost, even if temporarily routed through compatibility components;
- `cd frontend && npm run build` passes.

## 5. Phase 2 - Shared Admin mobile primitives

Create reusable Admin components inside `frontend/src/admin/` or shared `frontend/src/ui/` only when also useful outside Admin:

```text
AdminPageHeader
AdminListCard
AdminStatusBadge
AdminSearchField
AdminFilterChip
AdminBottomSheet
AdminStickyActions
AdminField
AdminTextarea
AdminSelect
AdminConfirmSheet
AdminToast
AdminLoadingState
AdminErrorState
AdminEmptyState
```

Do not use raw `<button>` styling ad hoc across new screens when `Button` or an Admin composed component covers it.

Implement exact mutation states:

```text
idle
saving
saved
error
```

Display Uzbek copy:

```text
Saqlanmoqda...
Saqlandi
Saqlanmadi
Qayta urinish
```

### Phase 2 gate

- new Admin primitives work in light and dark themes;
- focus states are visible;
- 44px target requirement passes;
- long Uzbek labels wrap at 320px;
- `npm run build` passes.

## 6. Phase 3 - Dashboard and More hub

Move/refactor current dashboard into:

```text
frontend/src/admin/dashboard/AdminDashboard.tsx
```

Render sections in this exact order:

```text
1. quick actions: + Savol / + Test / + Nazariya
2. E'tibor kerak
3. Kontent counts
4. Ko'rik
5. Mavzu qamrovi
6. So'nggi o'zgarishlar
```

Every actionable count deep-links to an already-filtered destination.

Create `MoreHub.tsx` with rows in this exact order:

```text
Ko'rik navbati
Shikoyatlar
Qoidalar
Media
Import / Bulk
Adminlar       # only admin/superadmin
Audit          # only roles permitted by backend policy
```

### Phase 3 gate

- dashboard loads with explicit loading/error/retry states;
- no `.catch(() => undefined)` is used for dashboard core data;
- every dashboard alert opens its corresponding filtered screen;
- More permissions hide unavailable surfaces but server security remains authoritative;
- frontend build passes.

## 7. Phase 4 - Question hub

Move/refactor question list into:

```text
frontend/src/admin/questions/QuestionHub.tsx
frontend/src/admin/questions/QuestionCard.tsx
frontend/src/admin/questions/QuestionFiltersSheet.tsx
```

### Exact mobile layout order

```text
Page title + add button
Search field
status shortcut chips
active filter chips
question cards
pagination/load-more control
```

Shortcut chips:

```text
Barchasi
Qoralama
Ko'rik
Muammo
```

Filter sheet fields in this exact order:

```text
Mavzu
Holat
Qiyinlik
Media turi
Yo'l belgisi savoli
Qoida
Tekshirish holati
Muallif
Reviewer
Ko'p xato qilinadi
Past aniqlik
Shikoyat bor
Dublikat gumoni
```

Question card order:

```text
topic + lifecycle badge
prompt, max 3 visual lines
media type + option count + linked Rule summary
accuracy + attempts + report count where available
Tahrirlash button + overflow menu
```

Overflow order:

```text
Preview
QA
Nusxa olish
Qoida(lar)ni ochish
Shikoyatlar
Arxivlash
```

Add/complete these backend contracts if missing:

```text
GET  /api/admin/questions/{id}
POST /api/admin/questions/{id}/duplicate
DELETE /api/admin/questions/{id}
```

`DELETE` means safe archive for published/used content and hard delete only for never-published unreferenced draft content.

### Phase 4 gate

- 1,000+ rows are not returned unbounded;
- question search/filter is server-side;
- mobile cards render without IDs as primary text;
- clone works;
- archive hides published question from learner selection while preserving historical version references;
- backend tests and frontend build pass.

## 8. Phase 5 - Question editor

Create:

```text
QuestionEditor.tsx
QuestionOptionsEditor.tsx
QuestionPreview.tsx
QuestionQA.tsx
```

### Exact mobile editor section order

```text
1. Asosiy
2. Media
3. Variantlar
4. Tushuntirish
5. Qoida va manbalar
6. Preview / QA
```

Do not render a permanent two-column layout below 768px.

### Asosiy fields

Render in this order:

```text
Mavzu
Submavzu (only if model supports it; otherwise omit, do not invent storage)
Qiyinlik
Yo'l belgisi savoli toggle
Savol matni
```

Category B is shown read-only or omitted; it is not editable in v1.

### Media section

Render:

```text
current media preview
Yangi yuklash / Media kutubxonasidan tanlash
Almashtirish
Olib tashlash
metadata: type, dimensions, duration, size
alt text
```

Never show `media_id` as the normal user-facing control.

### Options

Each option is a vertical card. Order inside each card:

```text
letter + correct selector
answer text
option explanation
move up / move down / remove
```

Rules:

- minimum 2 options;
- maximum 5;
- exactly one correct;
- labels recalculate after reorder;
- drag reorder may exist but up/down buttons are mandatory.

### Main explanation

Render `Eslab qoling` after options.

### Rules/sources

Rule picker is searchable. A selected Rule card shows:

```text
code
title/current text excerpt
status
verified_at
open
remove
```

Superseded/repealed Rule selection requires explicit warning confirmation.

### Autosave exact behavior

- first explicit `Saqlash` creates the draft/container;
- after a draft exists, edits autosave after `1500ms` of inactivity;
- editing a published question creates exactly one working draft version for that editor session;
- further autosaves update that working draft and do not fork new versions;
- display `Saqlanmoqda...`, `Saqlandi`, or `Saqlanmadi`;
- publish never occurs automatically.

Implement optimistic concurrency using `updated_at` or a revision token. Stale writes return HTTP `409`. UI copy:

```text
Bu kontent boshqa admin tomonidan o'zgartirilgan.
[ Yangisini ochish ]
```

### Sticky mobile actions

Exact order:

```text
Preview | Saqlash | Nashr etish
```

Hide `Nashr etish` if role does not permit it or validation fails.

### Preview

Below 768px open preview as a separate Admin route/sheet. Tabs exactly:

```text
Mashq | Imtihon | QA
```

Above 768px preview stays visible in the 360px right column while tabs remain available.

### Phase 5 gate

At 320px an admin can:

1. create a question;
2. upload/select media;
3. create 2-5 options;
4. choose one correct option;
5. write every explanation;
6. link a Rule;
7. save;
8. preview Practice and Exam;
9. publish if authorized;
10. leave and reopen it without data loss.

Also verify 409 conflict behavior and unsaved-change guard.

## 9. Phase 6 - Theory Admin mobile refactor

Create/refactor the exact files listed under `frontend/src/admin/theory/`.

### Theory hub order

Render exactly:

```text
Qidirish
Bo'limlar
Maqolalar
Yo'l belgilari
Yo'l chiziqlari
Regulirovshchik
Svetofor
```

Each row shows count and problem/reverification count.

Do not use six wrapped top tabs on mobile.

### Editors

Use these exact field orders.

#### Sign

```text
media preview
Kod
Oila
Nomi
Ma'nosi
Haydovchi nima qiladi?
Muhim ma'lumot
Ko'p uchraydigan xato
Eslab qolish
Qoidalar
Kalit so'zlar
Preview
```

#### Marking

```text
media preview
Kod
Guruh
Nomi
Ma'nosi
Kesib o'tish mumkinmi?
To'xtash/parkovka ta'siri
Qarama-qarshilik qoidasi
Qoidalar
Preview
```

#### Gesture

```text
static media preview
animation preview
Kod
Nomi
Holat tavsifi
Ruxsat etilgan
Taqiqlangan
Eslab qolish
Qoidalar
Preview
```

#### Traffic light

```text
media preview
Turi
Sarlavha
Ma'nosi
Harakat mumkinmi?
Yo'nalish
Istisnolar
Imtihon misoli
Qoidalar
Preview
```

#### Theory article

Section order:

```text
Asosiy
Hero media
Kontent bloklari
Qoidalar
Bog'langan savollar
Preview
```

`+ Blok` opens a sheet. Block choices order:

```text
Matn
Qoida
Rasm
Animatsiya
Diagramma
Ogohlantirish
Eslab qoling
Misol
Jadval
Mashq havolasi
```

Do not ask mobile admins to type JSON for a table. Implement rows/columns editor. Raw JSON is not part of normal Admin UI.

Use the same sticky save/archive mechanics as Question editor.

### Phase 6 gate

At 320px an authorized admin can create/edit/archive every Theory content type, upload/select media, link Rules, preview, and return using Telegram BackButton without losing dirty-state protection.

## 10. Phase 7 - Training Test/Assessment backend

Implement a dedicated training-assessment domain. Do not use `MockTemplate`, and do not use the official `MockAttempt` for these modes.

### Enums

Add exactly:

```text
AssessmentType:
  custom_test
  practice_ticket
  endurance_50
  endurance_100
  readiness_challenge
  daily_challenge

AssessmentSelectionMode:
  manual
  random_filter

AssessmentStatus:
  draft
  published
  archived

AssessmentAttemptStatus:
  in_progress
  completed
  expired
```

### Models

Add exactly these stable concepts:

```text
Assessment
  id
  slug unique
  type
  status
  current_version_id nullable
  created_by_user_id
  created_at
  updated_at
  archived_at nullable

AssessmentVersion
  id
  assessment_id
  version
  title
  description nullable
  selection_mode
  question_count
  time_limit_seconds nullable
  pass_correct nullable
  show_explanations_after enum(each_answer, completion)
  topic_filters_json nullable
  difficulty_filters_json nullable
  randomize_order bool
  authored_by_user_id
  created_at
  published_at nullable
  UNIQUE(assessment_id, version)

AssessmentQuestion
  id
  assessment_version_id
  question_id
  position
  UNIQUE(assessment_version_id, question_id)
  UNIQUE(assessment_version_id, position)

AssessmentAttempt
  id
  user_id
  assessment_version_id
  status
  started_at
  expires_at nullable
  completed_at nullable
  question_count
  correct_count
  passed nullable

AssessmentAttemptQuestion
  id
  assessment_attempt_id
  question_version_id
  position
  UNIQUE(assessment_attempt_id, question_version_id)
  UNIQUE(assessment_attempt_id, position)

AssessmentAnswer
  id
  assessment_attempt_id
  question_version_id
  selected_option_id nullable
  is_correct nullable
  answered_at nullable
  UNIQUE(assessment_attempt_id, question_version_id)
```

Use immutable published AssessmentVersions. Editing published assessment creates a new draft version.

### Attempt selection

For `manual`, take `AssessmentQuestion.question_id` in stored position order and resolve each to its current published QuestionVersion when the attempt starts.

For `random_filter`, compute eligible current published Question containers from the stored filters, uniformly choose `question_count` unique containers without replacement, then pin their current published QuestionVersions into `AssessmentAttemptQuestion`.

Historical attempts always render pinned QuestionVersions.

### API

Admin:

```text
GET    /api/admin/assessments
POST   /api/admin/assessments
GET    /api/admin/assessments/{id}
PUT    /api/admin/assessments/{id}
POST   /api/admin/assessments/{id}/publish
DELETE /api/admin/assessments/{id}
GET    /api/admin/assessments/{id}/eligible-count
```

Student:

```text
GET  /api/assessments
GET  /api/assessments/{slug}
POST /api/assessments/{slug}/attempts
GET  /api/assessment-attempts/{id}
POST /api/assessment-attempts/{id}/answers
POST /api/assessment-attempts/{id}/submit
GET  /api/assessment-attempts/{id}/review
```

Live attempt payload must not expose correctness/explanations before the configured reveal point.

### Migration

Create one additive migration for these tables/enums/FKs. Downgrade must remove only this assessment slice.

### Phase 7 gate

Backend tests must prove:

- manual assessment pins correct QuestionVersions;
- random assessment selects unique eligible questions;
- insufficient pool blocks publish/start;
- later question edits do not change old attempt;
- later assessment edits do not change old attempt;
- official `ExamConfig` is untouched;
- non-admin cannot use Admin assessment endpoints;
- active attempt does not leak answer keys.

Run full `pytest` before continuing.

## 11. Phase 8 - Testlar Admin UI

Create:

```text
AssessmentHub.tsx
AssessmentEditor.tsx
AssessmentQuestionSelector.tsx
AssessmentPreview.tsx
```

### Testlar root order

```text
Real imtihon protected system card
+ Yangi test
search
filter chips
assessment cards
```

The protected real-exam card displays read-only values from current `ExamConfig`:

```text
20 savol
25 daqiqa
18 to'g'ri
config version
last verified
```

Buttons:

```text
Preview
Manbani ko'rish
```

No ordinary Admin edit button exists for this card.

### New test wizard exact steps

```text
1. Turi va nomi
2. Savollar
3. Xulq-atvor
4. Preview
5. Nashr
```

Step 1 fields:

```text
Test turi
Nomi
Tavsif
```

Step 2 selection buttons:

```text
Qo'lda tanlash
Filtr bo'yicha random
```

Manual selector supports search + topic filter + selected-count indicator.

Random selector fields in order:

```text
Mavzular
Qiyinlik
Media talabi
Savollar soni
Mos savollar count
```

Disable publish when `eligible_count < question_count`.

Step 3 fields:

```text
Savollar soni
Vaqt limiti (optional)
O'tish chegarasi (optional)
Izohni ko'rsatish: har javobdan keyin | oxirida
Savollar tartibini aralashtirish
```

Type defaults:

```text
endurance_50  -> question_count = 50
endurance_100 -> question_count = 100
```

Those counts are locked for their respective types.

### Phase 8 gate

At 320px admin can create and publish both a manual and random-filter assessment, edit/archive it, and protected Real imtihon values remain uneditable.

## 12. Phase 9 - Media library

Create `MediaLibrary.tsx` and `MediaPicker.tsx`.

Backend contracts:

```text
GET    /api/admin/media
GET    /api/admin/media/{id}
POST   /api/admin/media
DELETE /api/admin/media/{id}
```

`GET /api/admin/media` supports:

```text
q
media_type
orphaned
uploaded_by
limit
cursor/page
```

Mobile media library order:

```text
Yangi yuklash
Qidirish
filters
2-column thumbnail grid at >=360px; 1 column at 320px if content cannot fit cleanly
```

Media detail displays:

```text
preview
type
size
dimensions
duration
content hash
uploaded by/date
usage count
linked content
orphan status
```

Delete is enabled only when backend confirms the media is safely orphaned and retention policy permits deletion.

Every Question/Theory editor media section must use this picker.

### Phase 9 gate

- existing media can be reused without re-upload;
- media upload works from mobile file chooser;
- list never downloads full animations until opened;
- delete cannot remove referenced media;
- frontend build + backend tests pass.

## 13. Phase 10 - Rules management

Create `RulesManager.tsx` and `RuleEditor.tsx`.

List filters/order:

```text
search
status
source
verified date
linked-content count
```

Rule detail order:

```text
code
status
current version
text/title
source URL/document
effective dates
verified_at
linked question count
linked Theory count
affected content
```

Actions:

```text
Yangi versiya
Supersede
```

Do not hard-edit a published rule version in place.

Superseding must trigger the existing needs-reverification propagation.

### Phase 10 gate

- Rule search works by code/text;
- linked counts are human-readable;
- supersede marks linked content for re-verification;
- non-admin role restrictions are enforced server-side.

## 14. Phase 11 - Review queue and reports

Refactor current screens into `operations/`.

### Review queue group order

```text
Savollar
Maqolalar
Belgilar
Chiziqlar
Ishoralar
Svetofor
Qayta tekshirish
```

Every row shows human title/prompt, author, age, linked Rule summary, lifecycle badge.

Open action goes to the exact editor/QA screen.

### Reports card order

```text
reason
human target title
number of grouped reports when grouped
latest report note/date
Open content
Triaged
Resolved
Rejected
```

Never show raw version UUID as the primary identity.

### Phase 11 gate

- review/report deep links work;
- resolving report refreshes the correct list;
- no silent catches on core loads;
- backend authorization tests pass.

## 15. Phase 12 - Global Admin search

Create `AdminSearch.tsx` and backend:

```text
GET /api/admin/search?q=&limit=&cursor=
```

Minimum result groups in order:

```text
Savollar
Testlar
Nazariya maqolalari
Yo'l belgilari
Yo'l chiziqlari
Regulirovshchik
Svetofor
Qoidalar
```

Search is debounced exactly `250ms`.

Selecting result pushes the exact Admin detail route.

Minimum query length: 2 characters. Empty/1-char query shows recent content or a prompt, not a full database dump.

### Phase 12 gate

- result groups navigate correctly;
- endpoint is permission-filtered and paginated;
- stale responses do not replace newer searches;
- frontend build passes.

## 16. Phase 13 - Admin users, audit, imports

### Admin users

Create `AdminUsers.tsx`.

Visible only to `admin`/`superadmin`; role changes requiring superadmin remain server-enforced.

Row displays:

```text
display name / Telegram identity available to admins
role
active/inactive
last activity
```

### Audit

Create `AuditLog.tsx` with filters:

```text
actor
action
entity type
date
search
```

Human sentence first, technical IDs collapsed below.

### Import/export

Create `ImportExport.tsx`.

Mobile import flow:

```text
Choose file
Upload
Validation summary
Row errors as collapsible cards
Commit
```

Never render a mandatory 20-column mobile table.

### Phase 13 gate

- privilege restrictions pass;
- audit filters work;
- invalid import cannot silently publish content;
- frontend build and backend tests pass.

## 17. Phase 14 - Wide-screen enhancement

Only after all mobile phases work.

At `>=768px`:

1. replace Admin bottom nav with left sidebar;
2. move quick create to top bar;
3. set Admin workspace max width to `1280px`;
4. Question/Theory editors become editor + 360px preview columns;
5. question/media/assessment lists may render compact table/list rows;
6. filter panel may remain open in a side column;
7. no mobile feature disappears.

Do not change domain behavior in this phase.

### Phase 14 gate

Check at `768x900` and `1024x900`:

- no consumer 640px constraint;
- sidebar visible;
- bottom nav hidden;
- editor preview side-by-side;
- all actions still reachable;
- no horizontal page overflow.

## 18. Phase 15 - Automated responsive tests

Add Playwright to the frontend dev dependencies:

```text
@playwright/test
```

Add package scripts:

```json
"test:e2e": "playwright test",
"test:e2e:admin": "playwright test tests/admin"
```

Create Admin E2E tests for these viewports:

```text
320x640
360x740
390x844
430x932
768x900
1024x900
```

Minimum Admin E2E scenarios:

```text
open Admin from Profile
navigate all five Admin destinations
open/close quick create
create question
question options fit and reorder
open preview
create Theory article
open sign editor
create manual assessment
create random assessment
open media library/picker
open Rules
open Review
open Reports
Telegram-style back stack behavior
unsaved-change guard
```

Every mobile viewport test must assert:

```text
document.documentElement.scrollWidth <= document.documentElement.clientWidth
```

Also verify sticky actions do not cover the last form field.

## 19. Phase 16 - Security and regression pass

Run/extend backend tests for:

```text
non-admin Admin API -> 403
role escalation blocked
IDOR blocked
stale revision -> 409
archive preserves historical references
media delete refuses referenced objects
assessment answer leak blocked
assessment historical version integrity
Rule re-verification propagation
Admin mutation audit event exists
```

Re-check Telegram authentication and do not alter its trust model.

## 20. Phase 17 - Final commands and completion gate

Run in this exact order:

```bash
pytest
cd frontend
npm install
npm run build
npm run test:e2e:admin
```

If Playwright browsers are not installed in the environment, install the required Chromium browser and rerun the E2E suite. Do not treat missing browser binaries as a test pass.

Then perform repository checks:

```bash
rg -n "className=\"card admin\"|admin-nav|admin-subnav" frontend/src
```

Old root wrapped-button Admin navigation must no longer be the active Admin architecture. Legacy class names may remain only if used by a non-navigation compatibility element and should preferably be removed.

## 21. Final required user journeys

Do not declare Admin complete until all of these can be completed on a 360px-wide viewport.

### Journey A - new question

```text
Profile
-> Admin
-> +
-> Savol
-> choose topic
-> enter prompt
-> add/select image or animation
-> create 2-5 answer options
-> choose correct option
-> write each explanation
-> write Eslab qoling
-> link Rule
-> Save
-> Preview Mashq
-> Preview Imtihon
-> Publish (authorized role)
-> return to question list
-> find the question by search
```

### Journey B - edit/remove question

```text
Savollar
-> search question
-> open
-> Tahrirlash
-> one working draft is created
-> edit
-> autosave
-> publish new version
-> archive
-> confirm it disappears from learner selection
-> historical attempts still render old pinned version
```

### Journey C - Theory

```text
Nazariya
-> Yo'l belgilar
-> open sign
-> edit explanation
-> replace/reuse media
-> link Rule
-> preview
-> publish/update
-> archive
-> restore
```

Repeat CRUD coverage in automated tests for article, marking, gesture, and traffic light.

### Journey D - training test

```text
Testlar
-> protected Real imtihon card is visible and uneditable
-> + Test
-> choose custom_test
-> choose manual selection
-> select questions
-> set behavior
-> preview
-> publish
-> create second random_filter test
-> verify eligible count
-> publish
```

### Journey E - operations

```text
Panel
-> open re-verification alert
-> exact content opens
-> fix/review
-> return
-> open report alert
-> exact content opens
-> resolve report
-> open media library
-> inspect usage
-> open Rule
-> inspect linked content
```

## 22. Final UI rules that are not optional

- Admin is visually a dedicated workspace, not a generic card inside the learner UI.
- Mobile comes first; desktop is only an enhancement.
- Exactly five primary Admin destinations.
- No nested six-button Theory tab strip on mobile.
- No desktop two-column editor below 768px.
- No raw IDs as primary list labels.
- No raw JSON editing in normal mobile Theory tables.
- No save button only at the bottom of a long form; sticky actions are mandatory.
- No silent API failure for core Admin screens.
- No horizontal page scrolling at required mobile widths.
- No unrestricted large list responses.
- No Admin-created test may modify or masquerade as the real `ExamConfig` simulation.
- No correctness/explanation leakage in active official mock or active assessment when configured to reveal only at completion.
- No published historical content is mutated in place.
- No client-side role check is treated as security.

## 23. Reporting after implementation

The implementation agent's final report must contain exactly these headings:

```text
1. Phases completed
2. Files created/changed
3. Database migration
4. Admin navigation
5. Questions workflow
6. Tests/assessments workflow
7. Theory workflow
8. Media and Rules
9. Review/reports/operations
10. Responsive test results by viewport
11. Backend test result
12. Frontend build result
13. Playwright result
14. Remaining blockers
```

`Remaining blockers` should be `None` unless an external legal/licensing/service dependency genuinely prevents completion. Do not list ordinary implementation work as a blocker.
