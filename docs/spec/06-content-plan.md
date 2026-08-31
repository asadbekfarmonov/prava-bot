# 06 — Content plan

## Topic taxonomy (YHQ)

The 15 learning topics (from research §6). These organise learning and practice filtering;
they are **not** a claimed exam blueprint — the official exam publishes no fixed per-topic
distribution ([01-exam-and-rules.md](01-exam-and-rules.md)).

| # | `Topic` key | Uzbek label | Notes / typical media |
| ---: | --- | --- | --- |
| 1 | `general_rules` | Umumiy qoidalar va haydovchi majburiyatlari | duties, documents, seat belts/helmets, post-accident |
| 2 | `road_signs` | Yo'l belgilari | **image-heavy**; source of the road-sign trainer pool |
| 3 | `road_markings` | Yo'l belgilanishlari | solid/broken lines, stop lines, crossings, arrows, temporary |
| 4 | `signals` | Svetofor va regulirovshchik signallari | lights, arrow sections, flashing, pedestrian, hand signals |
| 5 | `intersections` | Chorrahalar va imtiyoz | **animation/diagram**; regulated/uncontrolled, priority, turns |
| 6 | `manoeuvring` | Manevr va qatorlarni almashtirish | start, merge, lane change, reverse, signalling |
| 7 | `speed_distance` | Tezlik, masofa va to'xtash | speed limits, following/lateral distance, stopping distance |
| 8 | `overtaking` | Quvib o'tish | when allowed/prohibited, obstacles, visibility |
| 9 | `stopping_parking` | To'xtash va to'xtab turish | permitted/prohibited areas, near crossings/stops |
| 10 | `vulnerable_users` | Piyoda, velosipedchi va jamoat transporti | pedestrian priority, crossings, school zones, cyclists |
| 11 | `railway_crossings` | Temir yo'l kesishmalari | signals, barriers, stopping, forced-stop actions |
| 12 | `motorways_special` | Avtomagistrallar va maxsus sharoitlar | motorway rules, tunnels, slopes, residential zones |
| 13 | `vehicle_condition` | Transport vositasi holati va xavfsizligi | tyres, brakes, lights; when driving is prohibited |
| 14 | `transport_of_people_cargo` | Yo'lovchi va yuk tashish | passenger limits, child transport, loading, towing |
| 15 | `emergencies_first_aid` | Favqulodda vaziyatlar va birinchi yordam | current rules + recognised first-aid guidance only |

## Road-sign trainer content

The trainer (a **v1** feature — [03-features.md](03-features.md#road-sign-trainer-v1)) has
**no separate content pipeline**. It draws from ordinary `Question` records where
`topic = road_signs` and `is_sign_question = true`. Authoring a sign question is the same as
any other question; just set the flag. This keeps one bank, one authoring flow, one rule
model.

## Question targets for v1 launch

- All 15 topics represented.
- **30–50 verified original questions per major topic** where appropriate; smaller topics
  (e.g. railway crossings) may have fewer.
- Enough total variety that repeated 20-question mocks (uniform random, without replacement
  from the shared bank) do not become memorisation.
- The mock draws from the **same published bank** as practice — so the bank must be large
  enough that a 20-question sample is not near-deterministic. A practical floor is a few
  hundred published questions before promoting mock exams heavily.
- **Quality before quantity**: explanations and `Rule` links must be reliable before growing
  raw counts.

## Authoring workflow (admin studio)

For each question:
1. Choose category (B) and topic/subtopic; set `is_sign_question` for sign cards.
2. Write the prompt (Uzbek/Latin `QuestionTranslation`). Attach media if needed (sign image,
   intersection clip).
3. Add **2–5 options**, mark exactly one correct; write each option's text + explanation.
4. Write the `short_explanation` (one/two-sentence rule summary).
5. Link one or more **`Rule`** records (**required to publish**) — the YHQ clause(s) tested.
6. Optionally set `source_refs`, `verified_at`, difficulty (1–3).
7. Draft → review → publish. Publish validation enforces option/explanation/rule rules and
   at least one `QuestionRule`.

## Rule catalog governance

- Maintain a first-class **`Rule`** catalog (code, title, `text_uz`, `source_url`, effective
  dates, `verified_at`, `version`, `status`) — see
  [02-domain-model.md](02-domain-model.md#rule-model-legal-provenance).
- Questions link to rules via `QuestionRule` (many-to-many).
- When a rule changes: update/supersede the `Rule`, then list **all** linked questions
  (`QuestionRule` by `rule_id`) and re-review them. Bump `Question.content_version` /
  `verified_at` after re-verification.

## Content governance

- **Original questions only** for v1. Do not import a third-party/official bank until reuse
  rights and the technical source are confirmed (research §19).
- Never label internally authored content an **"official exam question."**
- **First-aid** content must come from current Uzbekistan rules and recognised first-aid
  guidance — not old question banks.
- If LLMs draft questions/explanations, a human verifies against the linked `Rule` before
  publishing.

## Media production notes

- **Signs**: static images (WebP after upload). Use official artwork only where reuse is
  permitted; otherwise redraw.
- **Intersections/manoeuvres**: short **looping muted MP4/WebM** or GIF; keep clips short and
  small (see media caps in [05-architecture.md](05-architecture.md)); stored in object
  storage, addressed by content hash.
- Always provide alt text for accessibility.

## Open content research (before scaling / v2)

From research §25: confirm the current YHQ text and stable clause identifiers for citations;
whether an official reusable question bank/images/animations may be reproduced; the
practical-exam exercise list and penalty matrix; regional prices; official exam-interface
languages; and any officially defined topic distribution.
