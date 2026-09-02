# 16 — Frontend / product redesign

A full redesign of the Telegram Mini App frontend: information architecture, navigation,
visual system, and every screen. Mobile-first for Telegram. This is a real product redesign,
not a recolor. Competitor density is used only as a feature-accessibility reference — **we do
not copy the competitor's neon-card visual design, layout, icons, wording, or assets.**

## Phase 1 — Audit of the current frontend (findings)

The current app (`frontend/src/main.tsx` + `styles.css`, single-file screens) is functional but
visually a developer tool:

1. **No navigation model** — Home is a vertical stack of ~8 identical blue/secondary buttons;
   every screen has a lone "back home" button. No bottom nav; no sense of place.
2. **Home is not a dashboard** — it answers none of the four key questions (readiness / what
   next / weak areas / start exam). No readiness, no exam countdown, no "continue", no
   recommendations, no daily goal.
3. **Question media is NOT rendered** — both Practice and Mock print the literal string
   `[media: <id>]` instead of an `<img>`/`<video>` from `/api/media/{id}/{hash}`. Seeded images
   are invisible. **Highest-impact bug to fix.**
4. **Raw enum labels** — the practice topic `<select>` shows `road_signs`, `intersections`,
   etc. (unlocalized keys).
5. **Explanations are a wall** — all option explanations + rule shown at once; no expandable
   "Nega C? / Nega A emas? / Qoida" sections.
6. **No design system** — `styles.css` is light-only, one blue accent, ad-hoc classes, no
   tokens, no dark theme, no skeletons, no intentional empty/error/offline states.
7. **Progress/Ranking look like data dumps** (bulleted lists / bare table), not consumer UI.
8. **Weak Telegram integration** — only `ready()` + `expand()`; no safe-area insets, no
   BackButton, no theme params, no viewport/keyboard handling.
9. **No skeleton/loading**, generic error strings (sometimes raw), no offline indicator.
10. **Mock mode** is reasonable structurally (bar/timer/navigator) but still shows `[media: id]`
    and isn't a fully isolated exam surface (it shares the button-stack chrome).

Conclusion: rebuild the shell, navigation, design system, and Home; refactor screens into a
shared component library; render media properly; add states. Do not preserve the button-stack.

## Phase 2 — Visual/product direction

Feeling: **simple · fast · confident · visual · exam-serious but daily-enjoyable.** Avoid
generic dashboards, developer tables, excessive borders, random bright colors, huge gradients,
childish gamification, tiny controls, desktop-first layouts, and the competitor's busy neon
cards.

Direction: clean neutral base; **one primary accent**; clear success/warning/danger; large
readable typography; consistent icon family (lucide-react, already a dependency option);
12–20px rounding; restrained shadows; strong hierarchy; minimal Home text; high-quality
media presentation; subtle progress visualization; restrained interaction feedback.
**Dark + light theme** driven by Telegram `themeParams` (fallback to system), via CSS tokens.

## Phase 3 — Navigation

**Bottom navigation, exactly 5 primary tabs:**

```
Home (Asosiy) · Practice (Mashq) · Theory (Nazariya) · Exam (Imtihon) · Profile (Profil)
```

- Ranking lives under Home (card) and Profile — not a primary tab.
- Mistakes, Road signs, Progress, Search, and the new practice modes are reached from Home /
  Practice hub, not the bottom bar.
- Bottom nav is **hidden in active mock exam** (Phase 12) and during onboarding.
- Use the Telegram **BackButton** for in-stack navigation (detail screens) instead of ad-hoc
  "back home" buttons; the bottom bar handles top-level switching.

## Phase 4 — Home (intelligent hub)

Home answers: *How ready am I? What next? What am I weak at? Can I start the real exam?*
Order of visual weight (one clear primary CTA — **Davom etish**):

```
Salom, {name}                         Imtihongacha {n} kun   (if exam_date set)
┌───────────────────────────── Readiness card (primary, elevated) ─────────┐
│ Imtihonga tayyorlik   78%   Yaxshi                                        │
│ Oxirgi mock: 18/20 · Ko'rilgan: 312 · Xatolar: 8 · 🔥 7 kun               │
│                            [ Davom etish ]                                │
└───────────────────────────────────────────────────────────────────────────┘
Bugungi maqsad   12/20   ████████░░
Siz uchun:  [ Chorrahalar · 61% → Mashq ]   [ Xatolar · 8 → Takrorlash ]
Tezkor kirish:  [ Nazariya ] [ Yo'l belgilari ] [ Real imtihon ] [ Reyting ]
```

- **Davom etish** is resolved by the backend "next action" (Phase / product-expansion §A):
  unfinished session → unresolved mistakes → weak topic → recommended daily work. The frontend
  calls a single endpoint and routes accordingly.
- Do NOT make 12 equally bright cards; exactly one accent surface (readiness), the rest neutral.
- **Content completion vs topic mastery vs exam readiness are distinct** and never conflated
  (no fake "100%"). Readiness comes from `07-readiness.md`.

## Phase 5 — Readiness card

Strongest component. States mirror `07-readiness.md`:

```
ready_estimate:  Imtihonga tayyorlik  78%  Yaxshi   + last 3 mocks (18/19/17)  [Batafsil]
initial:         Boshlang'ich daraja  63%           [Mashqni davom ettirish]
insufficient:    Hisoblash uchun yana 32 ta savol yeching   [Mashqni davom ettirish]
```

An animated progress ring (cheap, reduced-motion aware) shows the percentage. Never show fake
certainty; the "exam ready" badge only when the gate (incl. curriculum coverage) is met.

## Phase 6 — Practice

Focused single-question layout; localized topic label + progress:

```
Mavzu: Chorrahalar                              7 / 20
[ large media (image / animation) — real, not a placeholder ]
Savol matni
○ A …  ○ B …  ○ C …  ○ D …
[ Javob berish ]
```

After answering — **expandable** sections, not a wall:

```
✓ To'g'ri   /   ✕ Noto'g'ri  (Siz: A · To'g'ri: C)
▸ Nega C?          (expanded by default: correct-answer reasoning)
▸ Nega A emas?     (per wrong option, collapsed)
▸ Qoida — YHQ 13.9 [ Qoidani ko'rish → Theory ]
[ Keyingi savol ]
```

Selected/correct/wrong option states are clear and tactile. Practice-mode also hosts the new
modes surfaced from the Practice hub (Siz uchun / Mavzu bo'yicha / Xatolar / Belgilar / 50 /
100 / Biletlar / Real imtihon) per `17-product-expansion.md`.

## Phase 7 — Media container (images & animations)

A first-class `QuestionMedia` component (fixes the `[media: id]` bug):
- `image`/`gif` → `<img loading="lazy">`; `video` → `<video autoplay muted loop playsinline
  preload="metadata" poster>` with a **↻ Qayta ko'rish** replay control.
- Fixed aspect ratio box (no layout jump), skeleton while loading, graceful failure fallback,
  reduced-motion → show poster/first frame. Media is the visual focus, not squeezed into a
  small card. Source is always the content-addressed `/api/media/{id}/{hash}`.

## Phase 8 — Theory (Nazariya) — visual learning library

Prominent product surface (`14-theory-handbook.md`). Home shows a "continue lesson" card. Home
of Theory: search + section grid (sign/intersection/traffic-light/markings visuals). Articles:
title → short explanation → visual example → rule → common mistake → **practice** button;
short blocks, never a wall. Reuses the structured content blocks already built.

## Phase 9 — Road signs

Dedicated visual catalogue: responsive 2-col grid of sign images; instant search/filter by
family. Detail: code, name, large sign, meaning, driver action, common mistake, and
**"Shu belgi bo'yicha mashq"**. Uses the catalogue API already built.

## Phase 10 — Mistakes

Not a bare list — grouped by topic with counts + filters:

```
Xatolar — 8 ta takrorlash kerak
Chorrahalar 4 · Belgilar 2 · To'xtash 2
Filtr: [ Oxirgi ] [ Ko'p takrorlangan ] [ Barcha ]
[ Xatolarni takrorlash ]     Eng qiyin savollar → (separate list)
```

## Phase 11 — Mock exam entry (deliberate)

```
Real imtihon
20 savol · 25 daqiqa · 18 ta to'g'ri javob kerak
Imtihon davomida: tushuntirish yo'q · yordam yo'q · vaqt to'xtamaydi
[ Imtihonni boshlash ]
```

Not buried among practice cards; distinct from all training modes (50/100, tickets, readiness
challenge) which are clearly labelled "Bu real imtihon emas."

## Phase 12 — Mock exam visual mode (isolated)

Completely different character; when a mock is active: **hide bottom nav, streak, ranking,
recommendations, gamification, points; hide explanations/correct answers.** Plain, serious,
stable dark surface:

```
7 / 20                                   17:43
─────────────────────────────
        IMAGE / ANIMATION
─────────────────────────────
Savol…
○ A  ○ B  ○ C  ○ D
─────────────────────────────
1 2 3 4 5 6 [7] 8 … 20
[ Oldingi ]                 [ Keyingi ]
```

Timer always visible, calm; stronger (danger) treatment only near expiry (e.g. < 2 min). No
stress animations. Server-authoritative timer (`05`/`09`) unchanged.

## Phase 13 — Mock result

```
18 / 20   O'TDINGIZ
Vaqt 17:42 · To'g'ri 18 · Xato 2
Xatolar: 7. Chorrahalar · 14. To'xtash   [ Xatolarni ko'rish ]
Tayyorlik: 74% → 79%   (only if enough data)
[ Yana imtihon ]   [ Bosh sahifa ]
```

## Phase 14 — Profile

Consolidates identity/settings off Home: name · exam date (editable) · category · language ·
🔥 streak · questions answered · mock history · ranking position · settings · privacy
(ranking opt-out + custom public display name) · logout. Admin entry (role-gated) lives here,
not on Home.

## Phase 15 — Ranking

```
Reyting   [ Haftalik ] [ Oylik ] [ Umumiy ]
1. …  2. …  3. …   …   17. Siz (own row pinned, highlighted)
```

Uses the approved anti-farming points model; visually attractive but secondary. Opt-out +
custom display name respected (never leak Telegram username).

## Phase 16 — Progress / analytics

Readiness + last mocks + topic mastery bars (seen / accuracy / mastery distinct), strongest &
weakest topic, repeated mistakes. No meaningless charts to fill space.

## Phase 17 — Interaction details

Selected-answer states, loading **skeletons**, progress transitions, success/error feedback,
disabled states, tactile buttons, an animated progress ring (cheap, reduced-motion aware).
Restrained: a 20/20 mock may get a subtle success animation; normal practice stays calm. No
confetti spam.

## Phase 18 — Empty states (intentional, Uzbek)

```
Hali xatolaringiz yo'q. Mashqni davom ettiring.
Hali mock imtihon topshirmagansiz.  [ Birinchi imtihonni boshlash ]
Reyting uchun kamida 20 ta savol yeching.
```

Never a blank screen.

## Phase 19 — Loading / error / offline

Skeleton loading; retry buttons; offline indicator; buffered mock answers synced on reconnect
(`03`); media loading + graceful image failure. All messages in **Uzbek**, never raw backend
errors.

## Phase 20 — Design system (tokens + components)

CSS custom-property tokens (light + dark), set from Telegram `themeParams` when available:

```
--bg --surface --surface-2 --text --text-muted --border
--accent --accent-contrast --success --warning --danger
--radius-sm(12) --radius(16) --radius-lg(20) --shadow-1 --space-* --font-*
```

Shared components (replace per-screen ad-hoc CSS): Screen/AppBar, BottomNav, Card,
Button (primary/secondary/ghost/danger), StatBlock, ProgressBar, ProgressRing, QuestionMedia,
AnswerOption, Expandable, Badge, Chip/Filter, Tabs, BottomSheet/Modal, Skeleton, EmptyState,
Toast, ListRow, TopicMasteryBar. Ensure WCAG-AA contrast in both themes; min 44px touch targets.

## Phase 21 — Telegram Mini App UX

Use the WebApp SDK: `ready()`, `expand()`, `viewportStableHeight`, **safe-area insets**
(top/bottom), **BackButton** (show on detail screens; hook to in-app back), `themeParams` +
`colorScheme` for theming, `MainButton` optionally for primary CTAs, disable vertical swipe-to-
close during mock, handle keyboard/viewport resize, respect Android/iOS differences. No desktop
width assumptions.

## Phase 22 — Responsive targets

Primary widths **320 / 360 / 390 / 430 px**. Single-column, fluid; grids collapse to 2-up then
1-up; bottom nav fixed with safe-area padding; media scales without layout jump.

## Phase 23 — Accessibility

AA contrast; semantic roles; focus-visible; `aria-expanded` on expandables; alt text from
`QuestionMediaTranslation`; `prefers-reduced-motion`; keyboard operability; screen-reader
labels for icon-only controls.

## Implementation plan (order)

1. Design-system tokens + shared component library (`frontend/src/ui/`), dark/light, Telegram
   theme wiring; replace `styles.css` ad-hoc classes.
2. App shell: `AppBar` + `BottomNav` (5 tabs) + Telegram BackButton + safe areas; routing state.
3. **QuestionMedia** component (fix `[media: id]` → real image/video) — used by Practice, Mock,
   Theory, Sign detail.
4. Home dashboard (readiness card, countdown, daily goal, recommendations, quick access) +
   backend "next action"/home-summary endpoint (coordinate with `17`).
5. Practice redesign (localized topics, expandable explanations, media) + Practice hub of modes.
6. Theory + Road-signs redesign (grids, detail, search).
7. Mock: deliberate entry, isolated exam surface, result with readiness delta.
8. Progress + Ranking + Profile redesign.
9. States: skeletons, empty, error, offline; toasts.
10. Selected new **core** features from `17` (personalized practice, all-tests hub, exam
    countdown, topic mastery) integrated into the above.
11. Responsive pass (320–430) + accessibility pass.
12. Playwright e2e for key flows (Home → practice answer with media, mock happy path, theory
    nav, ranking) at mobile viewports.

Each step ships through the round-robin (backend_developer implement → tester + system_architect
review) and the pre-push gate (pytest, compileall, `npm run build`, e2e where touched).

## Guardrails

Do not copy competitor visuals. Do not conflate completion/mastery/readiness. Do not leak
answers in any question-embedding surface (Practice pre-answer, Mock, Theory practice_link,
exam preview). Keep exam mode plain and isolated. Uzbek copy throughout; ru-ready via the
existing i18n catalog.
