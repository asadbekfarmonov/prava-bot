# 15 — Road-sign, marking, controller & traffic-light catalogues

Structured catalogue entities that power the most visual Theory features. They plug into the
Theory framework ([14-theory-handbook.md](14-theory-handbook.md)) and reuse `Rule`/media/
versioning/search. Search/filter quality is the reason these are first-class structured
entities rather than generic articles.

## Verification (applies to every catalogue)

All codes, names, groupings, meanings, driver actions, gestures, light states, speed/distance
figures are **admin-authored and verification-required** against the current official
Uzbekistan YHQ / LexUZ. **Do not invent sign numbers or copy a commercial site's wording.** v1
seeds only clearly-marked **demo/original** placeholders; real content is authored + verified in
the admin studio. Sign graphics: use official artwork only where legally reusable, otherwise
faithful originals redrawn from the official definition — never labeled "official exam" imagery.

## Road signs

```
RoadSign                    # language-neutral identity + classification + media
  id
  official_code             str      # e.g. "1.20" — VERIFIED against YHQ; unique per catalog version
  family                    enum(warning, priority, prohibitory, mandatory,
                                  information, service, additional_plate)
  media_id                  -> QuestionMedia.id?      # the sign image (content-addressed)
  position                  int
  current_version_id        -> RoadSignVersion.id?
  lifecycle_status          VersionStatus

RoadSignVersion             # IMMUTABLE once published/used (published_at ⇒ locked)
  id, road_sign_id, version, status, media_id?, ai_assisted,
  authored_by/reviewed_by?/approved_by?, created_at, published_at?, verified_at?
  UNIQUE(road_sign_id, version)

RoadSignTranslation
  id, road_sign_version_id, language,
  name                      text
  meaning                   text
  driver_action             text     # what the driver must do
  important                 text?
  exam_trap                 text?     # common exam trap
  memory_tip                text?
  keywords                  text?     # search synonyms (uz), incl. transliterations
  UNIQUE(road_sign_version_id, language)

RoadSignRule                # sign version -> Rule(s), snapshot rule_version
  id, road_sign_version_id, rule_id, rule_version, UNIQUE(road_sign_version_id, rule_id)
```

Families (Uzbek labels for grouping, content verified separately):
`Ogohlantiruvchi · Imtiyoz · Taqiqlovchi · Buyuruvchi · Axborot-ko'rsatkich · Servis ·
Qo'shimcha axborot belgilar`.

### Sign detail card

```
[sign image]
1.20  <name>
Meaning: …
Nima qilish kerak: …
Muhim: …
Ko'p uchraydigan xato: …
[ Mashq qilish ]   → starts practice over questions linked to this sign
```

### Searchable sign library

- Search matches: `official_code`, uz `name`, `keywords`, `meaning`, and linked rule code.
  Queries like `parking`, `stop`, `piyoda`, `3.27`, `asosiy yo'l` all resolve.
- Filters (families): `All · Warning · Priority · Prohibition · Mandatory · Information ·
  Service · Additional plates`.
- Sign→question link uses the shared bank: signs relate to questions where
  `is_sign_question = true` (via a `RoadSignQuestionLink` analogous to
  `TheoryArticleQuestionLink`, or by matching the sign's rule/topic) so **Mashq qilish** starts
  the no-leak practice loop.

## Road markings

```
RoadMarking (+ RoadMarkingVersion + RoadMarkingTranslation + RoadMarkingRule)
  identity: id, code?, group enum(horizontal, vertical, temporary), media_id, position, versioning…
  translation fields: name, meaning, can_cross (text/enum-ish, verified), can_stop_park,
    conflict_rule (what wins when signs vs markings conflict — verified), exam_trap, memory_tip, keywords
```

Covers solid/broken/double lines, stop line, pedestrian crossing, directional arrows, lane
markings, yellow restrictions, temporary markings — each with "can you cross / stop-park?" and
the sign-vs-marking conflict rule, all verified.

## Traffic-light states

```
TrafficLightState (+ Version + Translation + Rule links)
  identity: id, kind enum(main, arrow_section, flashing, pedestrian, railway, special), media_id, position
  translation fields: title, meaning, movement_permitted (verified), direction_permitted,
    exceptions, typical_exam_situation
```

Covers red / yellow / green / red+yellow (if applicable) / flashing / arrow sections /
pedestrian / railway-crossing / Uzbekistan-specific special signals. Visual states/animations
via media blocks. Every state explains: meaning, whether movement is permitted, which direction,
exceptions, typical exam situation.

## Controller (regulirovshchik) gestures

Especially visual — users struggle to memorize these.

```
ControllerGesture (+ Version + Translation + Rule links)
  identity: id, code?, media_id (diagram), animation_media_id?, position, versioning…
  translation fields:
    position_desc      # arms / body facing / baton
    allowed            # cars from…, trams from…, pedestrians…
    forbidden
    memory_tip         # easy way to remember
```

Show a controller diagram from multiple driver viewpoints, an optional short **animation** of
the controller changing arm position, and a **Mashq qilish** button starting gesture-specific
questions.

## Priority / intersections, manoeuvres, speed, stopping, overtaking, etc.

These are delivered as Theory **articles** (structured content blocks: rule → diagram → example
→ common mistake → practice link) in [14-theory-handbook.md](14-theory-handbook.md), not as new
catalog tables — because they are explanatory lessons rather than enumerable catalog items.
Speed limits and key distances are best presented as `table`/`quick_ref` articles with an
explicit **`verified_at`** (values change and must be verified against the official source; do
not hard-code from memory).

## Search integration

All catalogue entries feed the global Theory search ([14](14-theory-handbook.md#search-global-theory-search))
with their code/name/keywords/meaning and linked rule code, filtered to published content for
students.

## Versioning & re-verification

Each catalogue entity is versioned (immutable once published) and links to `Rule`(s) with a
snapshotted `rule_version`. A rule change flips linked entries to `needs_reverification` into the
admin review queue — identical to questions and theory articles.

## Admin

The Theory admin area ([14](14-theory-handbook.md#admin-theory-editor-extends-the-studio)) gains
Signs / Markings / Gestures editors: upload media, author translations, link rules + questions,
set `verified_at`, review/publish immutable versions, all role-gated and audited.

## Tests

Sign catalogue listing + family filters; search by code/name/keyword/rule; sign→practice starts
linked questions (no answer leak); markings/gestures/lights list + detail; versioning +
rule-change→needs_reverification; admin author/review/publish + non-admin 403; media access via
content-addressed route; stored-XSS inert in translated fields; multilingual-ready (uz now, ru
additive).

## Content still needed (author + verify before launch — see §35 report)

- Complete verified sign set (codes, names, families, meanings, driver actions, traps) from
  official YHQ/LexUZ.
- Verified road-marking set + sign-vs-marking conflict rules.
- Verified traffic-controller gesture set (+ diagrams/animations).
- Verified traffic-light states incl. Uzbekistan-specific signals.
- Verified speed-limit + key-distance tables (category B), with `verified_at`.
- Medically-reviewed first-aid content (separate from legal post-accident steps).
