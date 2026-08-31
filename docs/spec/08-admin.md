# 08 — Admin experience

The admin studio will author hundreds–thousands of questions. It must be **fast and
comfortable for real content work**, not merely functional. All admin capability is gated by
role ([09-security.md](09-security.md)); every action is audited (`AdminAuditEvent`).

## Roles

`AdminRole` ([02-domain-model.md](02-domain-model.md#users-roles-profiles)):

| Role | Can |
| --- | --- |
| `content_author` | create/edit **draft** versions, upload media, submit for review, run imports to draft, report triage (view) |
| `content_reviewer` | everything an author can, plus **review/approve/publish**, resolve reports, manage the review queue |
| `admin` | reviewer + manage `Rule` catalog, bulk operations, archive, manage other authors/reviewers |
| `superadmin` | admin + assign roles, destructive/global operations, export/backup |

Separation-of-duties guidance: once the content team grows, an **author should not be the sole
approver of their own version**. v1 enforces a soft rule — publishing a version whose
`authored_by == approver` emits an audit warning; `admin`/`superadmin` may configure it to a
hard block (`require_second_reviewer = true` in admin config).

## Admin dashboard (home)

Immediately shows counts and actionable lists:

- **Content health**: total published questions; drafts; awaiting review; `reviewed` not yet
  published; **stale/unverified** (no `verified_at` or older than N months);
  **`needs_reverification`** (rule superseded — prominent).
- **Coverage**: questions per topic vs target; topics below target highlighted; questions
  **without media where media is likely needed** (e.g. `intersections`/`road_signs` topics
  with no `media_id`).
- **Quality**: questions with **validation errors**; **suspected duplicates**; **most-missed**
  and **low-accuracy** questions; **open content reports**.
- **Ops**: recently edited versions (who/when); **media-storage usage** (bytes, object count).

Prominent actions:

```
[ + New question ]  [ Import ]  [ Review queue ]  [ Rules ]  [ Media ]  [ Analytics ]  [ Reports ]
```

## Question editor

Fast, single-screen editor with a **live preview** beside it.

Fields:
- category, topic, subtopic, question type, **road-sign flag**;
- question text (Uzbek); short explanation / "Eslab qoling";
- **visual media** (image/video/gif) with inline upload + poster;
- **answer options** (2–5), **drag-and-drop reorder**, one clearly selected **correct** option;
- **explanation for every option**;
- **linked YHQ rule(s)** via the Rule picker (below);
- **supporting sources** (`QuestionVersionSource`);
- difficulty, status, content version (read-only: shows version number + `ai_assisted` flag).

Editing a **published** question creates a **new draft version** (immutability —
[02-domain-model.md](02-domain-model.md#question-container--immutable-versions)); the editor
makes this explicit ("Nashr etilgan savol — tahrir yangi versiya yaratadi").

### Live preview

Renders exactly like the learner screens, with a toggle:

```
[ Practice preview ]   [ Mock preview ]   [ Mobile preview ]
```

- **Practice preview**: shows explanations + rule (post-answer state).
- **Mock preview**: shows the exam-mode rendering ([12-ui-exam-mode.md](12-ui-exam-mode.md))
  with **no** answer/explanation reveal — so the author sees what the exam actually exposes.
- **Mobile preview**: Telegram narrow width.

## Rule picker

Admins never type YHQ references by hand. A **searchable** picker matches on code and text:

```
Qidiruv:  "to'xtash"   |   "13.9"   |   "chorraha"
→  YHQ 13.9 — <title> ...
```

On select it shows: rule code, current text, effective **version**, source, verification date.
Linking a **superseded/repealed** rule shows a warning and requires confirmation; the resulting
`QuestionVersionRule` snapshots the chosen `rule_version`.

## Review workflow & lifecycle

```
draft → needs_review → reviewed → published → superseded/archived
                                   ↘ needs_reverification (on rule change) → back to review
```

- Publishing requires **validation** (see Pre-publish QA) and reviewer/admin role.
- Every transition records the actor and time on the `QuestionVersion` (`authored_by`,
  `reviewed_by`, `approved_by`) and an `AdminAuditEvent`.
- A **Review queue** lists `needs_review` + `needs_reverification` with filters and one-click
  open-to-QA.

## Bulk operations

For 1,000+ questions, individual editing is not enough:

- **Import** CSV/JSON → **preview** (row-by-row) → **validation** → commit. Imports land as
  **draft** versions and **never auto-publish**; invalid rows are rejected and reported, not
  silently skipped.
- **Duplicate detection** runs during import (below).
- Bulk **topic change**, bulk **Rule linking** (only where safe — same topic/rule scope),
  bulk **status update**, bulk **archive**.
- **Export/backup** (JSON) of questions + versions + translations + rule links (superadmin).
- **Media batch upload** with mapping to questions by external key.

Import format carries external ids so re-imports update the right container and create new
versions rather than duplicating.

## Search and filters

Admins can filter by: question text; linked rule; topic; status; difficulty; **has
image/video**; **sign question**; verification date; author/reviewer; **most missed**; **low
accuracy**; **suspected duplicate**. Results are paginated with server-side limits
([09-security.md](09-security.md)).

## Duplicate detection

Assistive, never auto-destructive:
- **Normalized exact match** (whitespace/case/punctuation-insensitive on prompt + option set);
- **option-set similarity** (Jaccard on normalized option texts);
- **optional semantic similarity** (embedding cosine) as an admin hint only.
Flags candidates for human review; the system **never** auto-deletes based on similarity.

## Content reports queue

User reports ([02-domain-model.md](02-domain-model.md#content-reports)) land in a queue linked
to the **exact `question_version_id`** reported. Reasons: wrong answer, unclear explanation,
image problem, outdated rule, typo, other. Reviewer can open QA for that version, fix (new
version), and resolve/reject with a note.

## Pre-publish QA view

Before publishing, the reviewer sees a consolidated QA panel:

```
Savol · Media/animatsiya · Variantlar · To'g'ri variant
Har bir variant izohi · Qoida · Qoida matni · Manba · Tekshirilgan sana
[ Practice preview ]  [ Exam preview ]
```

Automated checklist (all must pass to publish):

```
✓ exactly one correct option
✓ 2–5 options
✓ current (non-superseded) rule linked
✓ explanation present for every option
✓ correct-answer reasoning present
✓ short "remember this" present
✓ uz translation complete (prompt + options + explanations)
✓ media accessible (loads from object storage) and, for video, plays with a poster
✓ no unresolved duplicate flag
✓ reviewer approved (and, if configured, reviewer ≠ sole author)
```

For visual questions the reviewer can **play the animation exactly as the learner will** and
confirm the explanation references the pictured situation (see explanation standard in
[06-content-plan.md](06-content-plan.md#explanation-quality-standard)).
