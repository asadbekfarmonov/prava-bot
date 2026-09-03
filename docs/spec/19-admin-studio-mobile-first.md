# 19 - Mobile-first admin studio

This spec defines the complete Admin Studio experience for `prava-bot`.

The existing admin implementation is functional, but it still behaves like a compact CRUD panel inside one card. The current root navigation is a wrapped row of buttons, editors rely on desktop-style two-column layouts that simply wrap on narrow screens, lists are mostly plain bordered rows, and there is no dedicated admin navigation model for a Telegram Mini App.

The goal of this spec is to turn Admin into a real mobile-first content studio that can comfortably manage questions, training tests, Theory, Rules, media, reports, and content quality from a phone.

This spec extends [08-admin.md](08-admin.md), [09-security.md](09-security.md), [14-theory-handbook.md](14-theory-handbook.md), [18-theory-production-completion.md](18-theory-production-completion.md), and the shared mobile design system in [16-frontend-redesign.md](16-frontend-redesign.md).

## 1. Product goals

An administrator should be able to complete the most common content tasks from a phone without needing a desktop browser.

Primary goals:

- add a new question in under two minutes when the content is ready;
- upload an image or animation directly while editing;
- preview the exact learner-facing Practice and Exam rendering;
- create and manage training tests without affecting the official real-exam simulation;
- add and edit Theory sections, articles, signs, markings, controller gestures, and traffic-light states;
- find any content quickly;
- edit or archive published content safely;
- handle reports and re-verification queues efficiently;
- remain fully usable at 320 px width;
- expand into a more productive wide layout on tablet/desktop without maintaining a separate admin application.

The Admin Studio remains part of the same React Telegram Mini App and FastAPI backend. It is not a second product.

## 2. Current implementation audit

The current admin implementation already provides useful foundations:

- role-aware access;
- question list/editor/QA;
- Theory management for sections, articles, signs, markings, gestures, and traffic lights;
- review queue;
- reports;
- Rule picker;
- media upload;
- immutable versioning and publish transitions;
- dashboard counts and topic coverage.

The main UX problems to fix are:

1. Admin is rendered inside one large `.card.admin` instead of a dedicated application shell.
2. Primary navigation is a wrapping button row. At narrow widths this becomes several rows and loses hierarchy.
3. Theory has another wrapping sub-navigation row with six items, creating nested tab clutter.
4. Question and Theory editors use side-by-side `editor-layout`; on mobile the preview moves underneath but the workflow is not redesigned for mobile.
5. Editor actions are not sticky, so long forms require scrolling back to save/publish controls.
6. Option editing uses dense horizontal flex controls that are awkward at 320-360 px.
7. Lists are plain rows instead of touch-friendly content cards with clear metadata/actions.
8. Search/filter controls permanently occupy vertical space instead of using compact filter chips and sheets.
9. There is no global admin search.
10. There is no quick-create action.
11. There is no dedicated Tests/Assessments management surface.
12. Media management is upload-only rather than a reusable media library.
13. Current admin-specific buttons do not consistently guarantee 44 px touch targets.
14. No admin-specific Telegram BackButton hierarchy is defined.
15. There is no unsaved-changes protection or draft autosave UX.

The implementation should be refactored rather than restyled in place.

## 3. Admin shell

When Admin is opened, replace the consumer shell with a dedicated `AdminShell`.

Do not render Admin inside a generic consumer card.

Suggested hierarchy:

```text
AdminShell
├── AdminTopBar
├── AdminRouteContent
├── AdminQuickCreateButton
└── AdminBottomNav
```

The consumer bottom navigation is hidden while Admin Studio is open.

### Admin top bar

Top bar contents:

```text
[ back/close ]   Admin                      [ search ] [ role/menu ]
                 Savollar / current section
```

Requirements:

- respects Telegram safe-area top inset;
- minimum 44 px height;
- current section title is always visible;
- optional small subtitle for context, for example `Savollar > #125`;
- global search icon available from every top-level Admin page;
- role/account menu gives access to role information, audit/settings where permitted, and `Adminni yopish`;
- Telegram BackButton mirrors in-app back behavior.

## 4. Mobile admin navigation

Use exactly five primary admin destinations:

```text
Panel
Savollar
Testlar
Nazariya
Ko'proq
```

Suggested labels/icons:

| Tab | Purpose |
| --- | --- |
| `Panel` | overview, alerts, quick actions |
| `Savollar` | question bank and question editor |
| `Testlar` | training tests, tickets, challenges, assessment definitions |
| `Nazariya` | Theory content management |
| `Ko'proq` | review queue, reports, Rules, media, imports, users/roles, audit |

The bottom bar must:

- use icon + short label;
- fit without horizontal scrolling at 320 px;
- keep each target approximately 44 x 44 px or larger;
- include safe-bottom padding;
- use `aria-current` for the active tab;
- never depend on hover.

### Wide-screen navigation

At `>= 768px`, Admin may replace the bottom bar with a left sidebar while retaining the same information architecture.

Suggested wide layout:

```text
┌──────────────┬─────────────────────────────────────────────┐
│ Admin        │ page top bar                                │
│ Panel        ├─────────────────────────────────────────────┤
│ Savollar     │                                             │
│ Testlar      │ current content                             │
│ Nazariya     │                                             │
│ Ko'proq      │                                             │
└──────────────┴─────────────────────────────────────────────┘
```

Do not create separate mobile and desktop implementations. The same routes/components reflow.

## 5. Quick create

Admins frequently create content. Provide one persistent quick-create action.

On mobile, use a floating `+` button above the bottom navigation. Tapping it opens a bottom sheet.

```text
Yangi qo'shish

[ Savol ]
[ Test ]
[ Nazariya maqolasi ]
[ Yo'l belgisi ]
[ Yo'l chizig'i ]
[ Regulirovshchik ishorasi ]
[ Svetofor holati ]
[ Qoida ]
```

Only show actions permitted by the user's role.

On wide screens this may become a visible `+ Yangi` button in the top bar.

Quick create should reduce navigation steps, not bypass validation or authorization.

## 6. Dashboard

The Admin dashboard should be action-oriented rather than a wall of statistics.

Recommended order:

```text
Admin

[ + Savol ]   [ + Test ]   [ + Nazariya ]

E'tibor kerak
- 12 qayta tekshirish kerak
- 7 ochiq shikoyat
- 4 media xatosi

Kontent
Savollar       1 245
Nazariya       86 maqola
Belgilar       180
Testlar        24

Ko'rik
8 ta kutmoqda                  [ Ochish ]

Mavzu qamrovi
...

So'nggi o'zgarishlar
...
```

Dashboard cards should deep-link to filtered lists.

Examples:

- tapping `12 qayta tekshirish kerak` opens the review queue filtered to `needs_reverification`;
- tapping `7 ochiq shikoyat` opens Reports filtered to open;
- tapping a topic in coverage opens Questions filtered by that topic.

Do not require admins to manually reproduce dashboard filters.

## 7. Global admin search

Add a global search surface accessible from the top bar.

Search across:

- question prompt;
- question ID/external key;
- Theory article title;
- Theory section;
- road-sign code/name;
- road-marking code/name;
- gesture name/code;
- traffic-light state;
- Rule code/text;
- Test title/code;
- content report target where meaningful.

Results are grouped by type:

```text
Savollar
  "Asosiy yo'lda..."

Nazariya
  Chorrahalarda imtiyoz

Belgilar
  3.27 To'xtash taqiqlangan

Qoidalar
  YHQ ...
```

Selecting a result opens the exact editor/detail screen.

Search must be server-side, paginated, permission-filtered, and debounced.

## 8. Questions hub

The `Savollar` tab should open a content-management hub rather than immediately showing a dense form.

Top structure:

```text
Savollar                              [ + ]

[ Qidirish... ]       [ Filtr ]

Barchasi  1245   Qoralama  12   Muammo  7

question cards...
```

### Question filters

Filter sheet should support:

- topic;
- status;
- difficulty;
- has media / no media;
- image / animation;
- sign question;
- linked Rule;
- verification state/date;
- author;
- reviewer;
- most missed;
- low accuracy;
- reported;
- suspected duplicate.

Active filters appear as removable chips below search.

Do not keep 10 select fields permanently visible on mobile.

### Question cards on mobile

Each row becomes a touch-friendly card:

```text
Chorrahalar                    Nashr etilgan

Asosiy yo'lda ketayotgan...

Rasm · 4 variant · YHQ 13.x
To'g'ri: 61% · 184 javob

[ Tahrirlash ]       [ ... ]
```

The overflow menu can include:

```text
Preview
QA
Duplicate
Archive
Open linked Rule
Open reports
```

Do not show internal UUIDs as primary content.

### Wide view

At `>= 768px`, the same data may render as a compact table/list with columns, but row actions and filters remain identical.

## 9. Question editor

Question creation must be optimized for a phone.

Do not use a desktop two-column editor as the primary mobile flow.

Use a single-column editor split into clear sections:

```text
Yangi savol

1. Asosiy
2. Media
3. Variantlar
4. Tushuntirish
5. Qoida va manbalar
6. Preview / QA
```

These may be collapsible sections or a stepper. The user must still be able to jump between sections.

### Question editor fields

#### Asosiy

- category, B locked in v1;
- topic;
- subtopic if supported;
- difficulty;
- sign-question flag;
- question prompt.

#### Media

- current media preview;
- `Rasm/animatsiya qo'shish`;
- replace;
- remove;
- upload progress;
- media type, dimensions, duration;
- alt text;
- replay button for animation.

Do not show raw `media_id` as the main UX.

#### Options

Render each answer option as a vertical card:

```text
A                                      [ To'g'ri ○ ]
[ Javob matni                         ]
[ Nega bu variant to'g'ri/noto'g'ri? ]
                                [ O'chirish ]
```

Requirements:

- 2 to 5 options;
- one clear correct selector;
- drag reorder where supported;
- always provide `Move up` / `Move down` buttons as a non-drag alternative;
- automatic A/B/C/D/E recalculation after reorder;
- explanations visually paired with their options.

#### Main explanation

- short explanation / `Eslab qoling`;
- optional broader correct-answer explanation if the domain model supports it.

#### Rules and sources

Use the searchable Rule picker.

Show selected rules as full cards, not raw codes only:

```text
YHQ 13.x
Current
Tekshirilgan: 2026-08-31
[ Ochish ] [ X ]
```

Supporting sources use structured entries.

### Sticky action bar

On mobile, editors use a sticky action bar immediately above the Admin bottom navigation:

```text
[ Preview ]                      [ Saqlash ]
```

After the draft is valid and the role permits publishing:

```text
[ Preview ]        [ Saqlash ]   [ Nashr etish ]
```

Do not make the user scroll to the end of a long form to save.

### Autosave

Implement safe draft autosave:

- autosave only after a container/draft exists;
- debounce approximately 1-2 seconds after changes;
- show `Saqlandi`, `Saqlanmoqda...`, or `Saqlanmadi` state;
- do not create a new immutable version on every keystroke;
- editing a published item forks exactly one working draft, then autosaves that draft;
- explicit publish remains a deliberate action.

### Unsaved changes

When leaving a dirty editor before the first draft save, show a confirmation.

Telegram BackButton must obey this guard.

## 10. Preview and QA

Preview should not permanently occupy half the phone screen.

On mobile, `Preview` opens a full-height sheet/screen with tabs:

```text
[ Mashq ] [ Imtihon ] [ Mobil ]
```

Practice preview shows post-answer explanations.

Exam preview hides correctness/explanations exactly as the live mock does.

For animation questions, playback must match learner behavior.

On wider screens the preview may appear beside the editor.

QA should be available from the same preview flow:

```text
Preview
QA checklist
Version history
```

## 11. Duplicate and clone question

Add `Nusxa olish` to question actions.

Cloning creates a new draft container with copied:

- topic;
- prompt;
- media reference;
- options;
- explanations;
- Rule links;
- sources.

The admin must change whatever is necessary before publish.

Duplicate detection remains advisory and should warn when creating or importing highly similar content.

## 12. Tests and exams management

Create a dedicated `Testlar` Admin area.

Important distinction:

The official-like `Real imtihon` remains the fixed system simulation defined by `ExamConfig`: 20 random unique published questions, 25 minutes, pass at 18/20. Admins do not create arbitrary replacements for that mode.

Admin-created tests are training/assessment content.

Supported test types should include:

```text
custom_test
practice_ticket
endurance_50
endurance_100
readiness_challenge
daily_challenge
```

The exact user-facing availability follows [17-product-expansion.md](17-product-expansion.md).

### Assessment model

Introduce a stable assessment definition rather than reusing `MockTemplate`, which was intentionally removed from the real mock architecture.

Suggested model:

```text
Assessment
  id
  slug
  type
  lifecycle_status
  current_version_id
  created_at
  archived_at?

AssessmentVersion
  id
  assessment_id
  version
  title
  description?
  selection_mode       manual | random_filter
  question_count
  time_limit_seconds?
  pass_correct?
  show_explanations_after
  topic_filters_json?
  difficulty_filters_json?
  authored_by_user_id
  published_at?
  created_at

AssessmentQuestion
  assessment_version_id
  question_id
  position
  UNIQUE(assessment_version_id, question_id)
```

For `manual`, admin chooses specific Question containers.

For `random_filter`, admin defines filters and question count. At attempt start, current published QuestionVersions are selected and pinned to that attempt.

Admin assessment definitions must never change the legal `ExamConfig`.

### Real exam configuration card

Inside `Testlar`, show the current real-exam configuration as a protected system card:

```text
Real imtihon
20 savol · 25 daqiqa · 18 to'g'ri
Config v1 · tekshirilgan 2026-08-31

[ Preview ] [ Manbani ko'rish ]
```

Normal content admins cannot edit it.

If official rules change, changing `ExamConfig` follows the controlled domain-config process, not ordinary Admin CRUD.

### Add test wizard

Tapping `+ Test` starts a mobile wizard:

#### Step 1: Type and identity

```text
Test turi
Nomi
Qisqa tavsif
```

#### Step 2: Question selection

Choose:

```text
[ Qo'lda tanlash ]
[ Filtr bo'yicha random ]
```

Manual selection opens a searchable multi-select question list with topic filters.

Random selection lets admin select:

- topics;
- difficulties;
- sign/media requirements if useful;
- number of questions.

Show an eligibility count before save:

```text
Mos savollar: 184
Kerak: 50
```

Prevent publishing if the eligible pool is too small.

#### Step 3: Behavior

Configure only behavior appropriate to that test type:

- question count;
- optional timer;
- optional pass threshold;
- explanations after each answer vs after completion;
- random order;
- visibility;
- start/end schedule if supported later.

#### Step 4: Preview

Show how the learner will see the test entry and one sample question flow.

#### Step 5: Publish

Authorized admins can `Saqlash` or `Saqlash va nashr etish`.

### Test list

Mobile cards:

```text
Bilet 12                         Nashr etilgan
20 savol · qo'lda tanlangan
312 urinish · 73% o'rtacha

[ Tahrirlash ] [ ... ]
```

Filters:

- type;
- status;
- question count;
- published/draft;
- most used;
- recently edited.

## 13. Theory admin navigation

The current Theory area has six wrap-around tabs. Replace that with a mobile-friendly Theory hub.

```text
Nazariya                              [ + ]

[ Qidirish... ]

[ Bo'limlar ]
[ Maqolalar ]
[ Yo'l belgilari ]
[ Yo'l chiziqlari ]
[ Regulirovshchik ]
[ Svetofor ]
```

Each is a large list row/card with count and problem badges.

Example:

```text
Yo'l belgilari
182 ta · 3 ta tekshirish kerak           >
```

Do not use six tiny tabs as the top-level mobile Theory navigation.

## 14. Theory article editor

Article editing uses the same mobile principles as Question editing.

Sections:

```text
Asosiy
Hero media
Kontent bloklari
Qoidalar
Bog'langan savollar
Preview
```

### Block editor

Each block is a vertical card.

```text
#3 Diagramma                         [ ↑ ] [ ↓ ] [ ... ]
[ media preview ]
[ izoh ]
```

`+ Blok` opens a bottom sheet:

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

Do not show every possible block-type button inline above the article on a 320 px screen.

For tables, provide a real small table editor instead of asking mobile admins to type JSON.

JSON may remain an advanced raw mode for superadmin/debug only.

## 15. Sign, marking, gesture, and light editors

Use tailored forms rather than one generic field-dump UX where it hurts clarity.

### Road sign editor

```text
[ large sign image ]
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
```

### Road marking editor

```text
[ marking diagram ]
Kod
Guruh
Nomi
Ma'nosi
Kesib o'tish mumkinmi?
To'xtash/parkovka ta'siri
Qarama-qarshilik qoidasi
Qoidalar
```

### Controller gesture editor

```text
[ static diagram ]
[ animation ]
Kod
Nomi
Holat tavsifi
Ruxsat etilgan
Taqiqlangan
Eslab qolish
Qoidalar
```

### Traffic-light editor

```text
[ visual ]
Turi
Sarlavha
Ma'nosi
Harakat mumkinmi?
Yo'nalish
Istisnolar
Imtihon misoli
Qoidalar
```

Each editor has media preview, replace/remove, sticky save, archive, and learner preview.

## 16. Rules management

Move Rules into `Ko'proq > Qoidalar`.

Rule list supports:

- code/text search;
- active/superseded/repealed filters;
- source filter;
- verification-date filter;
- number of linked questions/Theory items;
- affected-content count when superseded.

Rule detail:

```text
YHQ ...
Current version
Source
Effective dates
Verified at

Linked content
- 24 questions
- 3 articles
- 2 road signs

[ Yangi versiya ]
[ Supersede ]
```

Changing a Rule must preserve the existing re-verification propagation behavior.

## 17. Media library

Add `Ko'proq > Media`.

The current upload-only flow is not enough for hundreds of assets.

Media library should provide:

- thumbnail/grid view;
- search by filename/alt text/content type;
- image/video filter;
- upload date;
- uploaded by;
- usage count;
- linked content;
- orphan status;
- file size/dimensions/duration;
- preview;
- reuse existing media in another question/article;
- replace by creating a new immutable media object;
- safe orphan deletion subject to retention rules.

Mobile media picker used from editors should open the library with:

```text
[ Yangi yuklash ]
[ Mavjud media ]
```

## 18. Review queue

Review becomes a high-priority operational surface under `Ko'proq`, with badges also shown on the dashboard.

Group by:

```text
Savollar
Nazariya
Belgilar
Chiziqlar
Ishoralar
Svetofor
Qayta tekshirish
```

Each review card should show enough information to decide what to open:

```text
Savol · Chorrahalar
"Qaysi avtomobil..."
Author: ... · 12 min old
Rule: YHQ ...

[ Ko'rish ]
```

Review opens the same preview/QA view used by the editor rather than an unrelated screen.

For roles allowed to publish, provide a clear final action.

## 19. Reports

Reports live under `Ko'proq > Shikoyatlar`.

Cards should display human-readable target information instead of raw version IDs.

```text
Noto'g'ri javob
Savol: "Qaysi avtomobil..."
3 ta foydalanuvchi xabar berdi

[ Kontentni ochish ]
[ Ko'rib chiqilmoqda ]
[ Hal qilindi ]
```

Group duplicate reports about the same current content/version where practical.

Allow one-tap navigation to the exact affected version/editor.

## 20. Imports and bulk operations

Bulk operations remain important but are not the primary mobile workflow.

Place them under `Ko'proq > Import / Bulk`.

Support:

- CSV/JSON question import;
- production Theory sync/import where applicable;
- media batch upload;
- export;
- bulk topic/status/archive;
- duplicate preview.

On mobile:

- file upload works;
- validation summary is card-based;
- row-level errors are collapsible;
- do not render a 20-column table that forces page-level horizontal scrolling.

On desktop, a table/grid may be used.

## 21. Users and roles

For `admin`/`superadmin`, `Ko'proq > Adminlar` provides:

- admin user list;
- role;
- last activity;
- active/inactive state;
- role change where permitted.

Only superadmin can assign/remove high-privilege roles according to security policy.

The UI is a convenience. Server-side authorization remains mandatory on every endpoint.

## 22. Audit log

`Ko'proq > Audit` is available to appropriate roles.

Filters:

- actor;
- action;
- entity type;
- date;
- entity ID/search title.

Each entry should be human-readable:

```text
Asad updated Road sign 3.27
Today 13:42
Version 4 -> draft 5
```

Raw IDs may be shown in an expandable technical section.

## 23. Content status actions

Published content is immutable by version.

Admin UX should present simple actions without exposing implementation complexity.

For an existing published item:

```text
[ Tahrirlash ]
```

means:

```text
fork one editable version
-> edit the draft
-> publish it
-> old version remains historical
```

For removal:

```text
[ O'chirish ]
```

on published/used content should normally mean safe archive/unpublish:

```text
archive container/current version
-> disappears from student APIs
-> historical attempts/references stay valid
```

Never hard-delete historical content required by attempts.

For never-published unreferenced drafts, hard delete may be allowed.

Provide `Tiklash` for archived content where supported.

## 24. Built-in content

Built-in Theory/content added by trusted project seed/sync does not require a human admin approval click before becoming visible, as defined in [18-theory-production-completion.md](18-theory-production-completion.md).

However, the Admin Studio must treat built-in content as normal manageable content after creation:

- edit;
- create a new version;
- replace media;
- archive/remove from students;
- restore;
- inspect source/provenance.

Do not require editing JSON/Python files for routine operational changes.

## 25. Responsive behavior

The entire Admin Studio is mobile-first.

### Required test widths

At minimum test:

```text
320 px
360 px
390 px
430 px
600 px
768 px
1024 px
```

### 320-479 px

- one-column layout;
- bottom navigation;
- no page-level horizontal scrolling;
- sticky editor actions;
- filters use sheets;
- previews use separate sheet/screen;
- card lists instead of data tables;
- all primary controls at least 44 px high;
- input font size at least 16 px to prevent iOS zoom;
- labels wrap;
- long Rule/sign names wrap;
- action groups stack or wrap intentionally;
- no two controls become unusably narrow.

### 480-767 px

- still primarily one-column;
- selected forms may use two small columns for compact fields only;
- content grids can move to two columns;
- bottom navigation remains acceptable.

### >= 768 px

- Admin shell may use sidebar navigation;
- max Admin workspace can expand beyond the consumer app's current 640 px limit, for example 1100-1280 px;
- editor + preview may be side-by-side;
- lists may become tables;
- filter panel may remain visible beside content;
- all mobile functionality remains available.

The consumer `.ui-app { max-width: 640px }` must not permanently constrain desktop Admin. Introduce an admin-specific wide container at the breakpoint while keeping Telegram/mobile behavior unchanged.

## 26. Telegram Mini App behavior

Admin must work correctly inside Telegram on iOS and Android.

Requirements:

- use Telegram safe-area variables;
- BackButton navigates the Admin stack before closing Admin;
- do not use browser-only assumptions for navigation;
- file input/upload works from mobile file/photo chooser;
- keyboard opening must not hide the active field or sticky action bar;
- bottom nav respects keyboard and safe area;
- avoid `100vh` assumptions;
- scrolling remains natural inside the Mini App;
- no horizontal swipe conflict with primary navigation;
- theme remains compatible with Telegram light/dark mode.

Suggested navigation stack:

```text
Profile
-> Admin Panel
-> Savollar
-> Question 123
-> Preview
```

BackButton should reverse one level at a time.

## 27. Forms and touch ergonomics

All admin forms must follow:

- 44 px minimum touch target;
- 16 px minimum input font on mobile;
- labels above fields;
- useful helper/error text immediately below the relevant field;
- no placeholder-only labels;
- destructive buttons visually separated from primary save actions;
- radio/checkbox labels are fully tappable;
- file chooser has a visible custom button and preview;
- numeric values use suitable keyboard/input modes;
- date fields do not overflow iOS containers;
- textareas auto-grow within sensible limits where practical.

## 28. Loading, errors, and optimistic feedback

Every Admin screen has explicit:

```text
loading
empty
error
retry
success
```

states.

Do not silently use `.catch(() => undefined)` for core Admin data.

Use skeletons for list/dashboard loading.

Use toasts or inline status for successful mutation:

```text
Saqlandi
Nashr etildi
Arxivlandi
Media yuklandi
```

Raw backend exceptions should not be the primary user-facing copy.

## 29. Offline and poor connection behavior

Admin editing is sensitive to data loss.

If network is lost:

- show persistent offline indicator;
- disable publish/destructive actions requiring server confirmation;
- preserve unsaved form state in memory while the screen remains open;
- clearly show `Saqlanmadi` when autosave fails;
- allow manual retry;
- do not pretend a write succeeded.

A future local draft cache may be added, but v1 does not need to persist unpublished sensitive content indefinitely in browser storage.

## 30. Concurrent editing

Prevent silent overwrite when two admins edit the same working version.

Preferred approach:

- include `updated_at` or revision token in edit requests;
- backend rejects stale writes with `409 Conflict`;
- frontend shows:

```text
Bu kontent boshqa admin tomonidan o'zgartirilgan.
[ Yangisini ochish ]
```

Do not silently last-write-wins on important content.

## 31. Security requirements

All [09-security.md](09-security.md) requirements remain mandatory.

Admin-specific reminders:

- hidden frontend routes are not authorization;
- every admin endpoint verifies authenticated Telegram user + role;
- bulk/destructive actions need server-side role checks;
- correct answers are never exposed to ordinary users through admin endpoints;
- Admin APIs must not be callable by a non-admin session;
- file upload validation stays server-side;
- Rule/media IDs are validated, not trusted from client;
- mass assignment must be prevented;
- audit every mutation;
- rate-limit write-heavy endpoints;
- do not trust role values sent by React.

High-impact destructive actions should require a confirmation sheet describing exactly what will happen.

## 32. Suggested frontend component architecture

Refactor `frontend/src/admin.tsx` instead of continuing to grow one large file.

Suggested structure:

```text
frontend/src/admin/
  AdminShell.tsx
  AdminTopBar.tsx
  AdminBottomNav.tsx
  QuickCreateSheet.tsx
  AdminSearch.tsx

  dashboard/
    AdminDashboard.tsx

  questions/
    QuestionHub.tsx
    QuestionList.tsx
    QuestionFilters.tsx
    QuestionEditor.tsx
    QuestionOptionsEditor.tsx
    QuestionPreview.tsx
    QuestionQA.tsx

  assessments/
    AssessmentHub.tsx
    AssessmentEditor.tsx
    QuestionSelector.tsx

  theory/
    TheoryHub.tsx
    SectionManager.tsx
    ArticleEditor.tsx
    BlockEditor.tsx
    SignEditor.tsx
    MarkingEditor.tsx
    GestureEditor.tsx
    LightEditor.tsx

  rules/
    RulesManager.tsx

  media/
    MediaLibrary.tsx
    MediaPicker.tsx

  operations/
    ReviewQueue.tsx
    Reports.tsx
    ImportExport.tsx
    AuditLog.tsx
```

Keep shared visual primitives in `frontend/src/ui/`.

Do not duplicate Button/Card/Input components in Admin.

## 33. Suggested backend additions

Audit existing endpoints before adding duplicates.

Likely needed additions include:

```text
GET    /api/admin/search

GET    /api/admin/questions/{id}
DELETE /api/admin/questions/{id}              # safe archive/delete semantics
POST   /api/admin/questions/{id}/duplicate

GET    /api/admin/assessments
POST   /api/admin/assessments
GET    /api/admin/assessments/{id}
PUT    /api/admin/assessments/{id}
POST   /api/admin/assessments/{id}/publish
DELETE /api/admin/assessments/{id}

GET    /api/admin/media
GET    /api/admin/media/{id}
POST   /api/admin/media
DELETE /api/admin/media/{id}                  # only if safely orphaned

archive/restore endpoints for Theory entities where missing
list/detail endpoints for Rules and Admin users where missing
```

Use consistent pagination:

```text
limit
cursor or page
filters
sort
```

Do not return an unbounded 1,000+ item list to a phone.

## 34. Assessment attempt behavior

Admin-created assessments must preserve historical integrity.

At user attempt start:

1. resolve the selected Question containers according to the AssessmentVersion;
2. choose current published QuestionVersions;
3. snapshot/pin those versions into the attempt;
4. preserve order/config for that attempt;
5. future question edits do not alter the historical attempt.

Do not reuse `MockAttempt` for every training mode if doing so would blur official real-exam semantics.

A dedicated `AssessmentAttempt` may be introduced, or long untimed training may reuse `PracticeSession` if the behavior remains clear. Document the final choice during implementation.

## 35. Admin analytics

Do not build an enormous analytics product, but give admins useful content-quality signals.

Question list/detail may show:

- attempts;
- accuracy;
- skip rate if tracked;
- most selected wrong option;
- report count;
- recent trend;
- average answer time where reliable.

Test detail may show:

- attempts;
- completion rate;
- average score;
- average time;
- hardest questions.

Theory detail may show:

- views;
- practice starts;
- report count.

These metrics should inform content maintenance, not change legal answers automatically.

## 36. Accessibility

Admin must be usable with keyboard and screen readers where practical.

Requirements:

- semantic buttons/inputs/labels;
- visible focus state;
- headings form a logical hierarchy;
- status is not conveyed only by color;
- icon-only buttons have labels;
- bottom sheets trap focus appropriately on web;
- reorder has button alternatives;
- validation errors are announced/associated with fields;
- contrast follows the shared design tokens.

## 37. Performance

The admin experience should remain responsive with 1,000+ questions and hundreds of media assets.

Requirements:

- server-side pagination;
- debounced search;
- lazy media thumbnails;
- do not fetch full QuestionVersion bodies for list rows unless needed;
- cache stable lookups such as topic labels and current Rule metadata where sensible;
- abort/ignore stale searches;
- virtualize only if needed after measurement;
- avoid downloading animations in list views until preview/open.

## 38. Responsive acceptance tests

Add automated or Playwright viewport tests for:

```text
320x640
360x740
390x844
430x932
768x900
1024x900
```

At each mobile width verify:

- no page-level horizontal overflow;
- Admin bottom nav fits;
- quick-create sheet fits;
- question editor fields fit;
- answer option editor fits;
- media preview fits;
- sticky save bar does not cover the last field;
- Theory block editor fits;
- Test wizard fits;
- Rule picker fits;
- filter sheet fits;
- long Uzbek labels wrap;
- Telegram safe-area padding is applied.

## 39. Functional acceptance tests

At minimum cover:

### Navigation

- admin enters from Profile;
- consumer bottom navigation disappears;
- Admin bottom navigation works;
- Telegram BackButton reverses nested Admin routes;
- closing Admin returns to Profile safely.

### Questions

- create question from quick-create;
- upload media;
- add 2-5 options;
- select one correct answer;
- reorder options;
- link Rule;
- autosave draft;
- preview Practice/Exam;
- publish if authorized;
- edit published question creates one new version;
- duplicate question;
- archive question;
- archived question is hidden from students.

### Tests

- create manual assessment;
- search/select questions;
- create random-filter assessment;
- reject pool smaller than required count;
- preview;
- publish;
- user attempt snapshots QuestionVersions;
- editing the assessment later does not alter old attempts;
- real `ExamConfig` cannot be changed by ordinary assessment endpoints.

### Theory

- create/edit/archive each Theory type;
- article block editor works at mobile width;
- media picker works;
- preview works;
- built-in content can be edited without modifying source files.

### Operations

- review queue deep-link;
- reports open exact target;
- Rule update triggers re-verification as already specified;
- media library shows usage;
- non-admin is rejected server-side.

## 40. Implementation order

Recommended implementation sequence:

1. refactor Admin into `AdminShell` and route/state model;
2. implement mobile Admin bottom navigation and top bar;
3. implement quick-create sheet;
4. refactor Question list + mobile Question editor;
5. add sticky save/autosave/unsaved guard;
6. implement preview/QA sheet;
7. refactor Theory hub/editors for mobile;
8. implement Media library/picker;
9. implement `Testlar` assessment model/API/UI;
10. refactor review/reports/rules under `Ko'proq`;
11. add global admin search;
12. add wide-screen sidebar/table enhancements;
13. run responsive/accessibility/security tests.

Do not postpone mobile usability until after desktop Admin is complete. Each feature is implemented mobile-first and then enhanced for wider screens.

## 41. Definition of done

Admin Studio is complete for this scope when:

- Admin no longer renders as one nested generic card;
- dedicated Admin navigation exists;
- bottom navigation works at 320 px;
- quick create exists;
- question creation/editing is comfortable from a phone;
- preview/QA is mobile-appropriate;
- Theory is manageable without nested tab clutter;
- admins can create and manage training tests/assessments;
- real-exam domain config remains protected and separate;
- Rules and media have real management surfaces;
- reports/review queues deep-link to actual content;
- safe archive/remove semantics exist;
- built-in content remains editable from Admin;
- no core Admin list requires page-level horizontal scrolling;
- desktop Admin expands beyond the consumer 640 px container;
- all mutation endpoints remain role-gated and audited;
- responsive tests pass at all required widths;
- backend tests and frontend build/typecheck pass.
