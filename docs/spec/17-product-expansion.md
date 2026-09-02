# 17 — Product expansion

Evaluates competitor-density features (from the provided competitor analysis — we have no
screenshot and copy nothing from it) and decides what `prava-bot` builds, when, and how. Guiding
principle: **compete on quality, not button count** — verified YHQ rules, clear explanations
(every wrong option explained), high-quality visual/animated questions, strong Theory, realistic
mock, transparent readiness, cleaner UI, content versioning/review. Never ship empty/unreliable
features to match a competitor's count.

## Feature matrix

| Feature | Competitor | Our decision | Priority |
| --- | --- | --- | --- |
| Personalized practice ("Siz uchun") | Yes (Test yechish / Sizga mos savollar) | Build | **Core** |
| All-tests hub ("Mashqlar") | Yes (Barcha testlar) | Build | **Core** |
| Practice by topic | Yes | Build (exists) | **Core** |
| Mistake correction (modes) | Yes (Xatolarni tuzatish) | Improve (exists) | **Core** |
| Theory / textbook | Yes (Darslik) | Build (exists, 14/15) | **Core** |
| Road signs catalogue | Implied | Build strongly (exists, 15) | **Core** |
| Topics mastery | Yes (Mavzular 57%) | Build | **Core** |
| Real exam (20/25/18) | Yes (Real imtihon) | Build (exists, 01/12) | **Core** |
| Ranking | Our requirement | Build (exists, 10) | **Core** |
| Readiness | Yes | Build better (exists, 07) | **Core** |
| Exam countdown | Yes (kun qoldi) | Build | **Core** |
| Streak / daily goal | Yes (⚡ kun) | Build (exists) | **Core** |
| 50 / 100 endurance test | Yes (50/100 talik) | Build | **v1.1** |
| Tickets ("Biletlar") | Yes | Research + build | **v1.1** |
| Readiness challenge (100/200) | Yes (300 savol) | Build (our own) | **v1.1** |
| Daily challenge (Bugungi 20) | Implied | Build | **v1.1** |
| Audio explanation ("Ovozli sharh") | Yes | Evaluate/build | **v1.1** |
| Favorites / saved | likely | Build (14 seeds it) | **v1.1** |
| Achievements | Implied | Limited set | **v1.1** |
| Global search (theory/signs/rules) | Yes (header) | Build (14 has theory search) | **v1.1** |
| User content reports UI | our arch | Surface (exists, 08) | **v1.1** |
| Battle / PvP ("Oktagon") | Yes | Future "Duel" | **v2** |
| Friends / social | likely | Evaluate | **v2** |
| Instructor / driving-school mode | Yes (INSTRUKTOR) | Research B2B | **v2** |

## Per-feature analysis

Each: user value · complexity · data · security · decision.

### A. Personalized practice — "Siz uchun mashq" (Core)
- **Value**: highest-leverage study; the main daily action; also powers Home "Davom etish".
- **Complexity**: medium — a server-side selector over existing data.
- **Data**: reuse `PracticeAnswer`, `MistakeEntry`, `Question`/`QuestionVersion`, topic mastery.
  Selection priority: unresolved mistakes → weak topics (low mastery, ≥ sample) → unseen
  questions → stale (not seen recently) → under-covered topics. Weights in domain config.
- **Security**: same no-leak practice payload; server-side selection (client can't request an
  answer key).
- **Decision**: **Build now.** New endpoint `GET /api/practice/next-action` (also backs Home
  CTA) + a `source=personalized` practice session.

### B. All-tests hub — "Mashqlar" (Core)
- **Value**: one place to understand every mode; reduces maze feeling.
- **Complexity**: low (frontend hub) once modes exist.
- **UX**: `Siz uchun · Mavzu bo'yicha · Xatolar · Belgilar · 50 savol · 100 savol · Biletlar ·
  Real imtihon`. Never reveal answer keys pre-answer.
- **Decision**: **Build now** as the Practice tab landing; individual modes land per priority.

### C. Mistake modes (Core, improve)
- **Value**: targeted recovery; strong retention.
- **Data**: `MistakeEntry` (exists). Add filters: `Oxirgi` (recent), `Ko'p takrorlangan`
  (miss_count desc), `Barcha`; grouping by topic with counts.
- **Decision**: **Improve now** (UX from `16` Phase 10); backend already supports the queue.

### D. Theory / textbook (Core)
- Already specified (`14`/`15`). Make it a top-level tab and a Home "continue lesson" card.
- **Decision**: **Build/surface now** (already implemented; redesign UI).

### E. Tickets — "Biletlar" (v1.1, research)
- **Research**: In Uzbek/CIS driving prep, "biletlar" are traditional fixed numbered
  question sets (e.g. Bilet 1..N of 20). This is a **legacy learning convention**; the current
  automated exam forms its own 20-question set — so tickets are a **practice mode**, not the
  official exam structure. **Do not present tickets as the official exam generation** unless
  verified.
- **Value**: familiar to learners; structured coverage.
- **Complexity**: low–medium — deterministic partitioning of the published bank into fixed sets.
- **Data**: a `Ticket` grouping (or deterministic seed-based partition) over `Question`;
  per-user per-ticket progress. Versioning: tickets reference `question_version_id` snapshots or
  regenerate on bank change (decide at build).
- **Decision**: **v1.1**, clearly labelled a practice mode.

### F. 50 / 100 endurance test (v1.1)
- **Value**: broad knowledge check, weak-area discovery, revision endurance.
- **Complexity**: low — a longer practice session (no 25-min single timer, not pass/fail like
  the mock). Clearly "Bu real imtihon emas."
- **Data**: reuse practice; a `source=endurance` session of N questions; feeds progress/mastery
  and (optionally) ranking with anti-farm caps.
- **Decision**: **v1.1**.

### G. Real exam (Core)
- Exists (`01`/`12`); keep strongly distinct. **Build/keep now.**

### H. Audio explanation — "Ovozli sharh" (v1.1)
- **Value**: accessibility + learn-by-listening; a real differentiator if quality is good.
- **Complexity**: medium–high; content/quality risk for Uzbek.
- **Options**: (1) pre-generated reviewed audio (best quality, storage cost, authoring load);
  (2) TTS on demand (cheap, variable Uzbek quality); (3) reviewed TTS output cached. Store audio
  as media via the existing `MediaStorage` (content-addressed); attach to a
  `QuestionVersion`/explanation or `TheoryArticle`.
- **Security/cost**: no answer leak (audio only post-answer / in theory); storage + TTS cost.
- **Decision**: **v1.1**, do not block v1; never sacrifice explanation correctness for audio.
  Spec the accessibility benefit.

### I. Daily challenge — "Bugungi 20 savol" (v1.1)
- **Value**: retention; one curated/random daily set; completion → streak/ranking credit
  (respect anti-farm caps: daily challenge credited once/day).
- **Complexity**: low–medium (deterministic daily seed per user/day).
- **Decision**: **v1.1**.

### J. Streak / daily goal (Core)
- Exists. UI: `🔥 12 kun`; visible but not dominating exam prep. **Keep/surface now.**

### K. Achievements (v1.1, limited)
- **Value**: light motivation. Keep meaningful only: first mock, 20/20, 100 signs, 7-day streak,
  500 unique questions, all topics ≥70%. **No badge spam.**
- **Data**: derive server-side from existing facts + an `Achievement`/`UserAchievement` table.
- **Decision**: **v1.1**, small curated set.

### L. Battle / PvP — our "Duel" (v2)
- **Value**: engagement; viral. **Our own branding**, not "Oktagon".
- **Flow**: matchmake → same 10 questions → accuracy first, speed tiebreak → winner.
- **Complexity**: high — realtime/matchmaking, and **serious anti-cheat** (no answer leak,
  server-authoritative timing/scoring, no client-trusted results, rate/abuse limits, collusion
  detection).
- **Decision**: **v2**, not built without explicit approval.

### M. Friends / invite (v2)
- **Value**: retention; friend ranking; Telegram-native invite.
- **Risks**: spam mechanics — avoid. Privacy of progress sharing (opt-in).
- **Decision**: **v2**, evaluate.

### N. Instructor / driving-school mode (v2, B2B)
- **Value**: potential B2B revenue — instructors track students (progress, weak topics, mock
  history, readiness, assigned practice).
- **Complexity**: high — new user type/role, org model, invitations, data-sharing consent,
  authorization boundaries.
- **Decision**: **v2 / research**; document potential, do not build without approval.

### O. Exam countdown (Core)
- **Value**: urgency + workload guidance; cheap.
- **Data**: `StudentProfile.target_exam_date` (exists in onboarding scope). Home shows
  "Imtihongacha N kun"; optionally derive a recommended daily goal from days-remaining ×
  unseen-question volume.
- **Decision**: **Build now.**

### P. Readiness challenge (v1.1)
- **Value**: broad diagnostic across the curriculum; estimates readiness/weak areas — distinct
  from the official 20/25/18 mock. Our own concept: **"Tayyorlik tekshiruvi", 100 or 200
  questions**, clearly labelled "Bu real imtihon emas."
- **Complexity**: medium (long session + coverage-weighted selection + a diagnostic report that
  feeds readiness/weak-topics but is **not** a mock pass/fail).
- **Decision**: **v1.1**.

### Q. Global search (v1.1)
- **Value**: fast lookup across Theory, road signs, markings, rules, topics.
- **Security**: **no unrestricted public answer-key search over the question bank** — search
  covers theory/signs/rules/topics only; question-bank search stays admin-only (`08`).
- **Decision**: **v1.1** (theory search exists in `14`; extend to a global surface).

### R. Favorites / saved (v1.1)
- Save question / sign / rule / theory article for revision. `TheoryFavorite` exists in `14`;
  extend to questions/rules. **v1.1.**

### S. User content reports (v1.1)
- Backend + admin queue exist (`02`/`08`). Surface an accessible in-app report action:
  `Savolda xato bor · Tushuntirish tushunarsiz · Rasm ishlamayapti · Qoida eskirgan`.
- **Decision**: **v1.1** (UI surface).

## Roadmap

**Core (now, with the redesign):** frontend redesign + Home dashboard · personalized practice ·
practice by topic · mistakes (improved) · Theory · road signs · real exam · readiness ·
progress · ranking · exam countdown · streak/daily goal · all-tests hub · topic mastery.

**v1.1:** 50/100 endurance · tickets (researched, labelled practice) · readiness challenge
(100/200) · daily challenge · audio explanation (if quality/infra ready) · favorites ·
achievements (limited) · global search · reports UI · expanded analytics.

**v2:** PvP "Duel" · friends/social · instructor/driving-school (B2B) · advanced social.

## New data/config touched by Core features (for implementation specs)

- `GET /api/home` summary + `GET /api/practice/next-action` (personalized selector; backs Home
  CTA). Selection weights in `app/domain/exam_config.py`.
- `StudentProfile.target_exam_date` surfaced (countdown) — already in onboarding scope;
  ensure editable in Profile.
- Topic mastery already computable from `07` readiness inputs; expose a per-topic endpoint.
- No new legal/exam constants in env; all thresholds in domain config.

## Differentiators (do not regress while expanding)

Verified YHQ rules · explanation for every wrong option · high-quality media/animations · strong
Theory · strong mistake recovery · realistic mock · transparent readiness · cleaner UI · content
versioning/review. Feature growth must not introduce unverified content or answer-leak surfaces.
