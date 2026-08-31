# 06 — Content plan

## Topic taxonomy (YHQ)

The 15 learning topics (from research §6). These are for **learning organisation and
practice filtering**, not a claimed exam blueprint (the official exam publishes no fixed
per-topic distribution — see [01-exam-and-rules.md](01-exam-and-rules.md)).

| # | `Topic` key | Uzbek label | Notes / typical media |
| ---: | --- | --- | --- |
| 1 | `general_rules` | Umumiy qoidalar va haydovchi majburiyatlari | driver duties, documents, seat belts/helmets, post-accident |
| 2 | `road_signs` | Yo'l belgilari | **image-heavy**: warning/priority/prohibitory/mandatory/info/service/plates |
| 3 | `road_markings` | Yo'l belgilanishlari | solid/broken lines, stop lines, crossings, arrows, temporary |
| 4 | `signals` | Svetofor va regulirovshchik signallari | lights, arrow sections, flashing, pedestrian, hand signals |
| 5 | `intersections` | Chorrahalar va imtiyoz | **animation/diagram**: regulated/uncontrolled, priority, turns, U-turns |
| 6 | `manoeuvring` | Manevr va qatorlarni almashtirish | start, merge, lane change, reverse, signalling |
| 7 | `speed_distance` | Tezlik, masofa va to'xtash | speed limits, following/lateral distance, stopping distance |
| 8 | `overtaking` | Quvib o'tish | when allowed/prohibited, obstacles, visibility |
| 9 | `stopping_parking` | To'xtash va to'xtab turish | permitted/prohibited areas, near crossings/stops |
| 10 | `vulnerable_users` | Piyoda, velosipedchi va jamoat transporti | pedestrian priority, crossings, school zones, cyclists |
| 11 | `railway_crossings` | Temir yo'l kesishmalari | signals, barriers, stopping, forced-stop actions |
| 12 | `motorways_special` | Avtomagistrallar va maxsus sharoitlar | motorway rules, tunnels, slopes, residential zones |
| 13 | `vehicle_condition` | Transport vositasi holati va xavfsizligi | tyres, brakes, lights; when driving is prohibited; warning devices |
| 14 | `transport_of_people_cargo` | Yo'lovchi va yuk tashish | passenger limits, child transport, loading, towing, trailers |
| 15 | `emergencies_first_aid` | Favqulodda vaziyatlar va birinchi yordam | build from current rules + recognised first-aid guidance only |

## Question targets for v1 launch

- All 15 topics represented.
- **30–50 verified original questions per major topic** where appropriate; smaller topics
  (e.g. railway crossings) may have fewer.
- Enough total variety that repeated 20-question mocks do not become memorisation.
- **Quality before quantity**: explanations and `rule_refs` must be reliable before growing
  raw counts. A smaller, correct, well-explained bank beats a large unexplained dump.

## Authoring workflow (admin studio)

For each question:
1. Choose category (B) and topic/subtopic.
2. Write the prompt in Uzbek (Latin). Attach media if the situation needs it
   (sign image, intersection animation).
3. Add **2–5 options**, mark exactly one correct.
4. Write a **per-option explanation** (why each is right/wrong).
5. Write the `short_explanation` (one/two sentence rule summary).
6. Set **`rule_refs`** — the YHQ clause(s) the question tests (required to publish).
7. Optionally set `source_refs` and `verified_at`.
8. Set difficulty (1–3).
9. Draft → review → publish. Publish validation enforces the option/explanation/rule rules.

## Content governance

- **Original questions only** for v1. Do not import a third-party/official bank until reuse
  rights and the technical source are confirmed (research §19).
- Never label an internally authored question as an "official exam question."
- **First-aid** (`emergencies_first_aid`) content must come from current Uzbekistan rules and
  recognised first-aid guidance — not copied from old question banks.
- Keep `content_version` and `verified_at` so a rule change can flag affected questions for
  re-review.
- If LLMs draft questions or explanations, a human reviews and verifies against the cited
  rule before publishing.

## Media production notes

- **Signs**: static images (WebP after upload). Use official sign artwork only where reuse is
  permitted; otherwise redraw.
- **Intersections/manoeuvres**: short **looping muted MP4/WebM** or GIF showing the
  situation; keep clips short (a few seconds) and small (see media caps in
  [05-architecture.md](05-architecture.md)).
- Always provide `alt_text` for accessibility.

## Open content research (before scaling / v2)

Carried from research §25: confirm the current YHQ text and stable clause identifiers for
citations; whether an official reusable question bank/images/animations may be reproduced;
the practical-exam exercise list and penalty matrix; regional prices; official exam-interface
languages; and any officially defined topic distribution.
