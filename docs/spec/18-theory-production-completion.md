# 18 — Theory production completion

This spec closes the gap between the existing Theory/YHQ Handbook infrastructure and a production-usable learning section.

The architecture in [14-theory-handbook.md](14-theory-handbook.md) and [15-road-sign-catalogue.md](15-road-sign-catalogue.md) remains the base. The goal here is not another redesign of the domain model. The goal is to finish the feature end-to-end with populated content, visuals, explanations, progress, Theory↔Practice linkage, and complete admin management.

## Current implementation baseline

The repository already contains:

- Theory models and migration `0005`;
- student APIs for sections, articles, search, signs, markings, controller gestures, traffic-light states, favorites, progress, reports, and Theory→Practice;
- immutable Theory versions and audit metadata;
- Theory frontend screens;
- a road-sign manifest/import path;
- Theory admin service/API foundations.

The main remaining gap is product completeness: populated verified content, better visuals/explanations, stronger navigation, fully wired progress/favorites, Practice→Theory, and complete Theory CRUD in Admin.

## 1. Remove temporary/example naming globally

Temporary seed/example naming must disappear from production code, content, scripts, slugs, labels, IDs, docs, and UI.

Perform a repository-wide case-insensitive search using a pattern such as:

```bash
rg -ni "d[e]mo"
```

and eliminate all matches.

This includes filenames and identifiers that use the temporary marker.

Do not simply rename fake placeholder content and present it as real. Placeholder rules, fake codes, fake facts, and filler rows must be deleted or replaced with researched content.

Existing development databases need a safe cleanup/sync path that removes obsolete placeholder records without damaging real authored data.

Acceptance criterion: the repository-wide search above returns zero matches.

## 2. Ship populated Theory content

`Nazariya` must open as a useful driving-theory handbook, not as empty scaffolding.

Populate the major category-B areas:

1. Umumiy qoidalar va haydovchi majburiyatlari
2. Yo'l belgilari
3. Yo'l chiziqlari / belgilanishlari
4. Svetofor signallari
5. Regulirovshchik ishoralari
6. Chorrahalar va imtiyoz
7. Manevr qilish va qator almashtirish
8. Tezlik, masofa va to'xtash
9. Quvib o'tish
10. To'xtash va to'xtab turish
11. Piyodalar, velosipedchilar va jamoat transporti
12. Temir yo'l kesishmalari
13. Avtomagistrallar va maxsus sharoitlar
14. Transport vositasining texnik holati
15. Yo'lovchi va yuk tashish
16. YTH / favqulodda vaziyatda harakat
17. Birinchi yordam

Theory may use finer-grained sections than the shared `Topic` enum. Major areas such as road signs, intersections, traffic lights, parking, and manoeuvres should contain multiple useful lessons rather than one broad article.

## 3. Source and verification rules

Traffic-law facts must not be invented from model memory.

Use authoritative sources, prioritizing:

- current Uzbekistan YHQ / applicable Cabinet resolutions;
- LexUZ;
- Adliya/government guidance where appropriate;
- other official Uzbekistan government sources;
- authoritative medical/first-aid sources for first-aid content.

For sourced legal content retain provenance through the existing `Rule` model, including where available:

- source URL;
- source document;
- effective dates/version;
- verification date.

Student-facing content must not contain placeholder notes such as "needs verification", "sample", or equivalent filler.

Commercial preparation products may inform UX/research only unless a licence explicitly permits reuse.

## 4. Built-in Theory content publishes automatically

The initial built-in Theory content added by this implementation does not require a human admin to approve each item before it is visible.

Use a trusted bootstrap/sync path:

```text
verified source
→ structured import/seed
→ immutable version created
→ provenance stored
→ verified_at set
→ published/current
```

Keep audit/version metadata.

This does not remove admin controls. After bootstrap, admins must be able to edit, update, replace media, reorder, archive/unpublish, restore where supported, and otherwise manage the content.

## 5. Production Theory seed/sync system

Replace scattered temporary seed logic with a clear production content pipeline, for example:

```text
app/scripts/seed_theory.py
```

or:

```text
app/scripts/sync_theory_content.py
```

Requirements:

- idempotent;
- deterministic;
- safe to re-run;
- structured and maintainable;
- able to create missing built-in content;
- able to apply new built-in revisions without silently overwriting admin edits.

Prefer structured content files when appropriate, e.g.:

```text
app/content/theory/
  sections.json
  articles/
  signs.json
  markings.json
  traffic_lights.json
  controller_gestures.json
```

Track a stable built-in source key/revision so sync can distinguish upstream built-in updates from admin-modified current versions.

A safe policy is:

- create missing built-in entities;
- update only when the current version still corresponds to the prior built-in revision;
- never silently overwrite an admin-modified current version;
- report conflicts during sync.

## 6. Road-sign catalogue must be complete and useful

Audit the existing Uzbekistan sign manifest against the current official catalogue relevant to category-B preparation.

Each sign must provide:

- official code;
- current Uzbek name;
- family;
- large visual;
- sign-specific meaning;
- what the driver must do;
- important applicability/exception information where relevant;
- linked YHQ rule(s);
- provenance/source;
- verification date;
- searchable keywords.

Optional fields such as common confusion or memory tips should be used only when they add real value.

Do not use generic family-level explanations as the primary explanation for every sign.

A sign detail page should answer:

- What does this sign mean?
- Where/how does it apply?
- What should the driver do?
- Is there an important exception?
- Which current rule supports it?

## 7. Road-sign media and provenance

Every sign must have an actual visual.

The existing Wikimedia-based import path may be reused only where the specific asset is legally reusable.

For externally sourced media retain provenance metadata sufficient to identify:

- source URL/page;
- licence;
- attribution/author where required;
- retrieval/verification date.

Prefer official/public-domain or app-owned redraws when appropriate.

Do not hotlink production student media to third-party pages. Import through the existing media pipeline and serve through the configured object storage route.

## 8. Road markings

Populate the road-marking catalogue with the current markings a category-B learner needs.

Each marking should include, where applicable:

- code;
- image/diagram;
- name;
- meaning;
- whether it may be crossed;
- stopping/parking effect;
- temporary/permanent interaction;
- sign-vs-marking interaction;
- linked rule/source;
- plain-language explanation.

A marking entry without a useful visual is incomplete.

## 9. Traffic-light states

Populate all relevant current signal states, including as applicable:

- red;
- yellow;
- green;
- red + yellow;
- flashing signals;
- additional green arrow/section;
- pedestrian signals;
- railway signals;
- other special signals defined by current YHQ.

Each state/detail must include:

- visual;
- meaning;
- whether movement is permitted;
- permitted direction where applicable;
- exceptions;
- short example;
- linked current rule.

## 10. Controller gestures

Populate the current traffic-controller gestures required by Uzbekistan YHQ.

Each gesture must show:

- controller body/arm position;
- clear diagram;
- what vehicles from each relevant direction may do;
- what is prohibited;
- pedestrian behavior where relevant;
- tram behavior where relevant;
- memory explanation;
- linked official rule.

If a single image cannot explain the state, use multiple viewpoints or a short original animation.

Assets should be app-owned/original or legally reusable.

## 11. Theory lessons must teach, not merely restate law

Populate real articles using the existing structured block model:

- `text`;
- `rule_callout`;
- `image`;
- `diagram`;
- `animation`;
- `comparison`;
- `warning`;
- `memory_tip`;
- `table`;
- `example`;
- `practice_link`.

Preferred lesson pattern:

```text
rule/concept
→ visual example
→ reasoning
→ common confusion where useful
→ official source
→ practice action
```

For intersections and manoeuvres, use original diagrams with vehicles, arrows, lane geometry, and priority relationships.

For stopping/parking, show geometry/distances where applicable.

For speed rules, use concise tables/cards and verify every current numeric value before inserting it.

## 12. Explanation quality

Every concept should provide:

1. plain-language explanation;
2. visual where the concept is visual;
3. official rule/source;
4. example;
5. practical takeaway.

Avoid circular explanations and generic filler.

The user should learn how to recognize the situation and why the rule applies.

## 13. First aid

Finish the first-aid Theory section using authoritative current first-aid guidance.

Keep separate:

- legal post-collision/YHQ obligations;
- medical first aid.

Medical advice must be conservative, source-backed, and appropriate for driving-theory preparation.

Store the medical source separately from the YHQ legal source where necessary.

## 14. Theory frontend must be production-quality

Refactor `frontend/src/theory.tsx` into the shared design system rather than leaving it as nested generic cards.

Theory home should provide a polished mobile-first experience such as:

```text
Nazariya

[ Qidirish... ]

Davom ettiring
...

Asosiy bo'limlar
[ Yo'l belgilari ]
[ Chorrahalar ]
[ Svetofor ]
[ Regulirovshchik ]
[ Yo'l chiziqlari ]
[ Manevr ]
...

Tezkor ma'lumot
...

Saqlanganlar
...
```

Use relevant icons/thumbnail visuals and the shared UI tokens/components.

## 15. Quick reference

Implement `Tezkor ma'lumot` with concise verified references such as:

- speed limits;
- priority decision order;
- important stopping/parking distances;
- controller quick reference;
- sign families;
- important road markings;
- verified emergency actions/contacts where applicable.

Only use current verified values.

## 16. Theory progress

Wire the existing progress API completely.

Opening an article/sign/marking/gesture/light should mark it `viewed`.

Starting/answering linked practice should drive `practised`.

`mastered` remains server-derived from actual question performance.

The UI must clearly distinguish:

```text
viewed
practised
mastered
```

and show meaningful section/home rollups.

## 17. Favorites

Favorites must be fully functional.

Requirements:

- initial saved state loads correctly;
- add/remove is idempotent;
- duplicate-save behavior is safe;
- saved-items screen displays human-readable content, not raw IDs;
- clicking a favorite opens the actual item.

Example saved row:

```text
[sign] 3.27 — To'xtash taqiqlangan
Yo'l belgisi
```

## 18. Search and catalogue navigation

Every Theory search result must open the exact matched object.

Support dedicated routes/view state for:

```text
section/{slug}
article/{slug}
sign/{code}
marking/{id}
gesture/{id}
light/{id}
rule/{code}
```

User-facing result type labels must be Uzbek human-readable labels, not raw enum values.

Road signs need search by code/name/keywords plus family filters.

Road markings need useful group filters.

Large catalogues must not require blind scrolling.

## 19. Theory → Practice

Keep and strengthen the existing linked-practice flow.

Each relevant article/catalogue entry should expose linked questions.

Where safe, use the shared Rule graph to assist linkage:

```text
Rule
↕
QuestionVersionRule / question rule link
↕
TheoryArticleRule / RoadSignRule / catalog rule link
```

Do not require unnecessary manual duplication of links.

Show useful copy such as:

```text
Bu mavzu bo'yicha 14 ta savol
[ Mashq qilish ]
```

## 20. Practice → Theory

After a practice answer, especially after a wrong answer, expose:

```text
[ Qoidani o'rganish ]
```

Resolve via the existing `/api/theory/by-rule/{rule_code}` endpoint.

If several Theory entries cover the rule, show a compact chooser.

Desired flow:

```text
wrong answer
→ explanation
→ Theory
→ understand
→ return to practice
```

## 21. Theory content reports

Expose the existing Theory reporting API in the student UI.

On article/sign/marking/gesture/light detail screens provide a subtle reporting action with reasons such as:

- Noto'g'ri ma'lumot
- Tushuntirish tushunarsiz
- Rasm noto'g'ri
- Qoida eskirgan
- Imlo xatosi
- Boshqa

## 22. Complete Theory Admin UI

The backend Theory authoring foundations exist, but the frontend Admin must become a complete content-management experience.

Add a `Nazariya` area with at least:

```text
Nazariya
├── Bo'limlar
├── Maqolalar
├── Yo'l belgilari
├── Yo'l chiziqlari
├── Regulirovshchik
├── Svetofor
└── Media
```

For every Theory content type, admins must be able to:

- list;
- search/filter;
- open;
- edit;
- replace media;
- change order;
- change linked rules;
- change linked questions;
- save/update;
- archive/remove from student visibility;
- restore where supported.

Add missing backend list/detail/archive/restore endpoints as needed.

## 23. Removal semantics

Published/versioned content must be removed safely:

```text
Remove
→ archive/unpublish
→ disappears from student APIs/UI
→ historical references remain intact
```

Never physically delete a published version that may be referenced by historical/user data.

Hard deletion is acceptable only for never-published, unreferenced drafts.

## 24. Editing built-in content

Built-in bootstrap content must remain editable from Admin.

Editing a published item should preserve immutable history:

```text
current published version remains immutable
→ fork/create next version
→ edit
→ publish/make current
```

The initial built-in content does not need manual approval before first publication, but operational edits must still preserve version/audit history.

Provide a convenient authorized save/update flow for admin/superadmin rather than forcing source-file edits.

## 25. Media quality

Theory media must be intentional and relevant.

Do not ship:

- random stock placeholders;
- unrelated filler images;
- broken remote hotlinks.

Requirements:

- correct sign/marking visual;
- clear controller diagrams;
- useful intersection diagrams;
- reasonable resolution;
- responsive sizing;
- correct alt text;
- existing object-storage/media pipeline.

## 26. Loading, empty, error, retry

Do not hide network failures with `.catch(() => undefined)` and then present an empty catalogue.

Every major Theory screen needs explicit:

- loading;
- empty;
- error;
- retry states.

Reuse shared UI components (`Skeleton`, `EmptyState`, `Button`, `Card`, etc.).

## 27. Telegram Mini App navigation and responsiveness

Test at:

```text
320px
360px
390px
430px
```

Ensure:

- grids fit;
- images are not clipped;
- tables scroll locally where needed;
- long names wrap;
- filter chips remain touch-friendly;
- no page-level horizontal overflow;
- Telegram safe areas are respected;
- Telegram BackButton navigates one Theory level backward before leaving Theory.

## 28. Update existing specs

Update stale statements in:

- `14-theory-handbook.md`;
- `15-road-sign-catalogue.md`;
- `08-admin.md`;
- `README.md`;
- any other conflicting spec.

New product decision:

```text
v1 ships populated, researched Theory content.
Built-in Theory content is published automatically.
Admin approval is not required before initial built-in content appears.
Admin can edit/archive/remove it afterward.
```

Do not confuse source verification with admin approval.

## 29. Completeness acceptance criteria

Theory is not complete until:

- all major Theory sections are present and published;
- sections contain useful lessons rather than placeholders;
- road-sign catalogue is audited for completeness;
- signs have actual images and sign-specific explanations;
- road markings are meaningfully populated with visuals;
- controller gestures are populated and visual;
- traffic-light states are populated and visual;
- intersection/manoeuvre lessons include visual examples;
- speed/stopping numeric rules are current and source-backed;
- Theory search works;
- progress works;
- favorites work;
- Theory→Practice works;
- Practice→Theory works;
- Theory reports work;
- Admin can edit every content type;
- Admin can archive/remove every content type;
- student APIs expose active content only;
- no student-facing placeholder content remains;
- the repository-wide temporary-marker search returns zero matches.

## 30. Automated completeness checks

Add tests that fail if the Theory feature regresses into an empty shell.

At minimum cover:

- all required Theory sections exist after production bootstrap;
- required sections have published content;
- road signs have media;
- sign meanings are non-empty and sign-specific;
- no temporary/fake sign or Rule codes remain;
- markings catalogue is populated;
- gestures catalogue is populated;
- traffic-light catalogue is populated;
- published articles contain meaningful blocks;
- built-in content has source/provenance;
- built-in content is visible without a manual review click.

Also add a CI check for the temporary marker using the regex shown in §1.

## 31. Admin tests

Cover:

- admin lists Theory content;
- admin edits built-in article;
- admin replaces sign media;
- admin archives sign;
- archived sign disappears from student API;
- restore works where implemented;
- historical version remains intact;
- non-admin cannot edit/remove;
- initial built-in content does not require manual approval.

## 32. Frontend/e2e tests

Cover at least:

- open `Nazariya`;
- open section/article;
- render image;
- render rule explanation;
- open/filter/search sign catalogue;
- open sign detail;
- favorite/unfavorite;
- open saved item;
- open marking;
- open controller gesture;
- open traffic-light state;
- Theory→Practice;
- wrong Practice answer→Theory;
- report Theory issue;
- admin edit/archive.

## 33. Validation before completion

Run the full backend test suite and frontend build/typecheck/lint/e2e commands configured in the repository.

At minimum:

```bash
pytest
cd frontend && npm run build
```

Fix failures caused by this work rather than ignoring them.

## 34. Completion report

When implementation is complete, report:

1. files changed;
2. obsolete placeholder content removed;
3. Theory sections populated;
4. article count;
5. road-sign count;
6. road-marking count;
7. controller-gesture count;
8. traffic-light-state count;
9. images/animations added and licensing/provenance strategy;
10. official sources used;
11. Theory frontend improvements;
12. Theory↔Practice linkage;
13. Admin Theory functionality;
14. archive/remove behavior;
15. tests added;
16. backend/frontend validation results;
17. confirmation that the repository-wide temporary-marker search returns zero matches.
