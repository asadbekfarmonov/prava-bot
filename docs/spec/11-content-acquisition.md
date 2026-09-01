# 11 — Content & media acquisition strategy

We need theory questions, answer options, correct answers, road-sign images, intersection
diagrams, illustrations, and animations. This spec defines **where to look**, the **legal
principle**, and a fully-specified **original-content fallback**.

> Research status: the items marked **UNVERIFIED** below could not be confirmed in this pass
> (no live web access here). They are **research targets**, not established facts, and must be
> checked by a human before any acquisition decision. Do not treat any third-party bank as
> reusable just because it is visible online.

## Build decision: content source is replaceable (locked)

The app is built **content-source-agnostic**. v1 ships with **original / demo questions**
authored in the admin studio so development is never blocked, while licensing outreach runs in
parallel. The choice of source — original, demo, or a licensed bank — must **not** change the
application architecture; it only changes which rows populate the shared question bank.

### Content ingestion abstraction

All content enters through **one** validated path into `Question` + immutable
`QuestionVersion` ([02-domain-model.md](02-domain-model.md)):

```
ContentSource (adapter)
  ├── manual admin authoring        (v1 default)
  ├── CSV/JSON import               (08-admin.md)
  └── licensed-bank importer        (added only if/when a licence is signed)
        → maps external fields → QuestionVersion + translations + options + rule links + media
        → runs the SAME publish validation (2–5 options, exactly one correct,
          rule provenance, explanation per option, human verification)
        → lands as DRAFT; never auto-publishes
```

Because every source funnels through the same model, publish validation, and media pipeline,
swapping or adding a source is an **import-adapter + data** change, not an architecture change.
Provenance is recorded via `QuestionVersionSource` (and `ai_assisted` for LLM-drafted demo
content). This mirrors the storage adapter pattern (`MediaStorage`) — infrastructure choices
stay behind a port.

## Parallel licensing track (non-blocking)

Licensing is a **business/legal track that runs alongside development** and does **not** gate
the build. For each candidate provider (§2) collect: #questions, media coverage, languages,
official-claim status, explanations present?, licence terms (store / display / modify /
translate / commercial / duration / updates / ownership / redistribution), price model, and
contact/route. A signed licence later becomes a **licensed-bank importer** feeding the same
ingestion path above — with no change to the app's architecture.

## Guiding legal principle

**Visible online ≠ reusable.** We do not scrape or copy any third-party/official question
bank, image, or animation merely because it is publicly viewable. Reuse requires an explicit
right (public-domain/open licence, licence/API, purchase, or partnership). If a source's terms
prohibit automated copying/redistribution/commercial use, we state that and do not use it.

## 1. Official sources to investigate (first priority)

Check whether the officially approved theory question bank and/or associated media is
available publicly, by request, by licence/API, by partnership, or for purchase:

| Source | What to check | Status |
| --- | --- | --- |
| Ministry of Internal Affairs / **YHXX** (traffic safety service) | official question bank, exam media, licence/partnership route | **UNVERIFIED** |
| Ministry of Justice / **advice.adliya.uz** | rule texts, clause ids, reuse terms (already cited in research) | rules cited; reuse terms **UNVERIFIED** |
| **LexUZ** (lex.uz) | authoritative YHQ legal text for `Rule` catalog | **UNVERIFIED (reuse terms)** |
| Licensed exam organizations / private exam centres | whether they license their bank/media | **UNVERIFIED** |
| Official driving-school (avtomaktab) materials | approved textbook/media, reuse rights | **UNVERIFIED** |
| Government open-data portals (data.gov.uz, my.gov.uz) | open datasets for signs/questions | **UNVERIFIED** |
| Driving-school **software providers** (the vendors behind exam terminals) | licensable question+media packages | **UNVERIFIED** |

Deliverable for each: availability channel, licence terms, cost, update cadence, contact.

## 2. Existing preparation products (market + potential licensing references)

Investigate as **references** (and possible licensing partners) — record fields, do **not**
scrape:

| Product (to investigate) | Fields to record | Status |
| --- | --- | --- |
| **YHQ Test** (e.g. yhq-test.uz) | #questions, media, languages, claims-official?, explanations?, terms, licensing contact | **UNVERIFIED** |
| **Hayda** | same | **UNVERIFIED** |
| yolharakatiqoidalari-related products | same | **UNVERIFIED** |
| Current YHQ apps on Google Play / App Store | same | **UNVERIFIED** |
| Other major local driving-test systems | same | **UNVERIFIED** |

For each record: number of questions; media availability (images/animations); languages;
whether they **claim** official questions; whether explanations exist; **licensing/terms**;
whether reuse/scraping/redistribution/commercial use is permitted; and the contact/licensing
route. **If terms prohibit automated copying, state that explicitly and do not copy.**

## 3. Partnership / licensing route

Licensing an existing bank + images + animations may be far cheaper/faster than recreating
1,000+ visual questions. If we pursue it, the contract must specify our rights to:

- **store** the content;
- **display** it to end users;
- **modify / translate** (Uzbek Latin now, Russian later);
- **commercial use**;
- **duration** and **territory**;
- **updates** (do we receive rule-change updates?);
- **ownership** of derivatives/translations;
- **redistribution restrictions** and attribution obligations.

Record the counterpart, licence scope, cost model, and termination terms. Nothing here is
agreed yet — these are the terms to negotiate.

## 4. Original-content fallback pipeline (fully specified — safe default)

If official/licensed media cannot be obtained, author original content. This is the **default
we can build without external rights**:

```
current YHQ rule (Rule catalog, cited to LexUZ/adliya)
 → question author drafts prompt + options + correct answer
 → original diagram/animation built from our reusable asset system (below)
 → per-option explanations + short "remember this"
 → link Rule(s) (QuestionVersionRule) + supporting sources
 → reviewer QA (pre-publish checklist, 08-admin.md)
 → publish (immutable QuestionVersion)
```

Never label original visuals or questions as "official exam" content
([00-overview.md](00-overview.md)).

### Reusable graphical asset system

To generate many original diagrams without illustrating each from scratch, define a shared,
consistent library (SVG source at authoring time → exported to raster/animation for delivery;
note delivered media rejects live SVG per [09-security.md](09-security.md)):

- vehicle icons: **car** (multiple colors for "blue car / red car" references), **truck**,
  **bus**, **tram**, **motorcycle**, **bicycle**;
- **pedestrian** figures; road workers;
- **road/lane primitives**: straight, curve, T-junction, cross, roundabout, lane dividers;
- **traffic lights** (states + arrow sections); **traffic-controller** poses;
- **arrows** (movement/trajectory), **road markings**, **signs** (our redrawn set);
- crossings, stop lines, obstacles.

Diagrams composed from these assets keep a consistent visual language across the bank and let
authors describe situations by color/position that the explanation can then reference (e.g.
"Ko'k avtomobil asosiy yo'lda" — see the explanation standard in
[06-content-plan.md](06-content-plan.md#explanation-quality-standard)).

### Animations

Author short, looping, muted clips (MP4/WebM) from the same asset system for intersection and
manoeuvre situations. Keep them short/small (media caps, [05-architecture.md](05-architecture.md)).

## Open acquisition questions (need human/legal/business decision)

1. Is there an **officially reusable** question bank / sign / animation set, and on what terms?
2. Can we license from an **existing product** (YHQ Test / Hayda / others) — scope and cost?
3. Are **LexUZ / adliya** rule texts reproducible in-app (attribution requirements)?
4. Do any candidate sources' terms **prohibit** automated copying (then excluded)?
5. Build-vs-buy decision for the initial ~1,000-question visual bank.
