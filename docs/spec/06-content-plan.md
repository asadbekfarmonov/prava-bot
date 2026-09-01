# 06 — Content plan

## Topic taxonomy (YHQ)

The 15 learning topics (research §6). They organise learning/practice and define the
**curriculum coverage** required for readiness ([07-readiness.md](07-readiness.md)); they are
**not** a claimed exam blueprint — the official exam publishes no fixed per-topic distribution
([01-exam-and-rules.md](01-exam-and-rules.md)).

| # | `Topic` key | Uzbek label | Notes / typical media |
| ---: | --- | --- | --- |
| 1 | `general_rules` | Umumiy qoidalar va haydovchi majburiyatlari | duties, documents, seat belts/helmets, post-accident |
| 2 | `road_signs` | Yo'l belgilari | **image-heavy**; road-sign trainer pool |
| 3 | `road_markings` | Yo'l belgilanishlari | lines, stop lines, crossings, arrows, temporary |
| 4 | `signals` | Svetofor va regulirovshchik signallari | lights, arrows, flashing, pedestrian, hand signals |
| 5 | `intersections` | Chorrahalar va imtiyoz | **animation/diagram**; priority, turns, U-turns |
| 6 | `manoeuvring` | Manevr va qatorlarni almashtirish | start, merge, lane change, reverse, signalling |
| 7 | `speed_distance` | Tezlik, masofa va to'xtash | limits, following/lateral/stopping distance |
| 8 | `overtaking` | Quvib o'tish | when allowed/prohibited, obstacles, visibility |
| 9 | `stopping_parking` | To'xtash va to'xtab turish | permitted/prohibited areas, near crossings/stops |
| 10 | `vulnerable_users` | Piyoda, velosipedchi va jamoat transporti | pedestrian priority, crossings, school zones |
| 11 | `railway_crossings` | Temir yo'l kesishmalari | signals, barriers, forced-stop actions |
| 12 | `motorways_special` | Avtomagistrallar va maxsus sharoitlar | motorways, tunnels, slopes, residential zones |
| 13 | `vehicle_condition` | Transport vositasi holati va xavfsizligi | tyres, brakes, lights; when driving is prohibited |
| 14 | `transport_of_people_cargo` | Yo'lovchi va yuk tashish | passenger limits, child transport, loading, towing |
| 15 | `emergencies_first_aid` | Favqulodda vaziyatlar va birinchi yordam | current rules + recognised first-aid guidance only |

## Explanation quality standard

Explanations are the product's biggest differentiator. **Empty explanations are prohibited**
(e.g. "B is correct because B is the correct answer"). After answering in practice (and in
mock review), the learner should see:

```
Sizning javobingiz: A
To'g'ri javob: B

Nega B?
[concrete, specific reason grounded in the pictured situation and rule]

Nega A emas?
[specific reason this option is wrong]   (one per wrong option)

Qoida:
YHQ 13.9  →  [rule text from RuleTranslation]

Eslab qoling:
[short memorable heuristic]
```

For **visual** questions, explanations must reference the **actual diagram**, not a generic
legal paragraph:

```
Ko'k avtomobil asosiy yo'lda ketmoqda...
Qizil avtomobil oldidagi belgi "yo'l bering"ni bildiradi...
```

This is why the asset system uses consistent, describable elements (colored cars, named signs)
— see [11-content-acquisition.md](11-content-acquisition.md#reusable-graphical-asset-system).

### Requirements before publishing (enforced)

A version cannot be published unless it has:
- correct-answer reasoning;
- an explanation for **every** wrong option;
- a linked **current** (non-superseded) `Rule` via `QuestionVersionRule`;
- a short learner-friendly summary ("Eslab qoling");
- **human verification** (`reviewed_by`/`approved_by`) and a `verified_at` date.

These map 1:1 to the pre-publish QA checklist in
[08-admin.md](08-admin.md#pre-publish-qa-view).

### LLM assistance policy

If an LLM helps draft a question or explanation:
- it may use **only** the stored `Rule`/source text and the question context;
- it **never** decides which answer is correct;
- it **never** publishes automatically;
- a human reviewer approves it;
- the draft version is marked `ai_assisted = true` for audit
  ([02-domain-model.md](02-domain-model.md#question-container--immutable-versions)).

## Rule catalog governance

- Maintain a first-class **`Rule`** catalog (language-neutral) with **`RuleTranslation`** for
  text/title, plus `source_url`, effective dates, `verified_at`, `version`, `status`
  ([02-domain-model.md](02-domain-model.md#rule-model-translation-ready-legal-provenance)).
- Question **versions** link to rules via **`QuestionVersionRule`**, snapshotting the linked
  `rule_version`.
- When a rule is superseded/repealed, all question versions linked to an older `rule_version`
  become **`needs_reverification`** and surface in the admin dashboard for re-review; they are
  not silently treated as verified.

## Road-sign trainer content

The v1 trainer draws from ordinary questions where `topic = road_signs` and
`is_sign_question = true` — **no separate pipeline** ([03-features.md](03-features.md#road-sign-trainer-v1)).

## Question targets for v1 launch

- All 15 topics represented (required for readiness coverage).
- **30–50 verified original questions per major topic** where appropriate; smaller topics fewer.
- The mock draws uniformly at random (without replacement) from the shared published bank, so
  the bank must be large enough that a 20-question sample is not near-deterministic — a
  practical floor of a few hundred published questions before promoting mocks heavily.
- **Quality before quantity**: reliable explanations + rule links before growing raw counts.

## Content governance

- **Original / demo questions** for the v1 build so development is not blocked; the content
  source is **replaceable** via the ingestion adapter, and a licensed bank (if obtained) feeds
  the same path ([11-content-acquisition.md](11-content-acquisition.md#build-decision-content-source-is-replaceable-locked)).
  Do not import third-party/official banks until reuse rights and the technical source are
  confirmed.
- Never label internally authored content an **"official exam question."**
- **First-aid** content from current Uzbekistan rules + recognised first-aid guidance only.
- Keep version `verified_at`/`content_version` so rule changes can trigger re-review.

## Media production notes

- **Signs**: static images (WebP after upload); official artwork only where reuse is permitted,
  else redrawn from the asset system.
- **Intersections/manoeuvres**: short looping muted MP4/WebM or GIF; small; object storage,
  content-addressed ([05-architecture.md](05-architecture.md)).
- Always provide alt text (via `QuestionMediaTranslation`).

## Open content research (before scaling)

See [11-content-acquisition.md](11-content-acquisition.md) and research §25: current YHQ text
+ stable clause ids; reusable official bank/media rights; practical-exam details; regional
prices; official exam-interface languages; any official topic distribution.
