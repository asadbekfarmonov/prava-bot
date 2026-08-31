# 07 — Readiness score

Readiness answers "how likely is this user to pass the real theory exam?" It must **not** show
a confident percentage after a handful of questions, and it must **not** award "exam ready"
without **broad curriculum coverage**. All thresholds/weights are **domain configuration**
(alongside the exam config in [01-exam-and-rules.md](01-exam-and-rules.md)) — never env vars.

## Diagnostic is NOT readiness

The optional onboarding **diagnostic** (10 questions) never produces an
`Imtihonga tayyorlik` (exam readiness) percentage. Its output is a raw score plus topic
guidance only:

```
Boshlang'ich natija: 7/10

Kuchli mavzular:
- Yo'l belgilari
- To'xtash va to'xtab turish

Mashq qilish kerak:
- Chorrahalar
- Quvib o'tish
```

The diagnostic seeds topic recommendations and the weak-topics list. **`Imtihonga tayyorlik`
only appears once the readiness state reaches `ready_estimate`** (below). This wording is
consistent across [03-features.md](03-features.md) and [00-overview.md](00-overview.md).

## Display states

1. **`insufficient_data`** → `Ma'lumot yetarli emas` ("Not enough data"). No percentage, no
   badge. (The diagnostic result may still be shown separately as `Boshlang'ich natija`.)
2. **`initial`** → `Boshlang'ich daraja: 63%` ("Initial level"). A number, framed as initial;
   no "exam ready" badge.
3. **`ready_estimate`** → `Imtihonga tayyorlik: 81%`. The **"exam ready"** badge appears only
   if the advisory gate (below), including **curriculum coverage**, is satisfied.

## Configuration

```yaml
readiness:
  # state gating
  min_unique_questions_for_display: 40
  min_unique_questions_for_full:   100
  min_mocks_for_full:                3
  # component windows / samples
  recent_mock_count:                 5
  recent_window_days:               30
  topic_min_answers:                 5     # answers needed for a topic to COUNT in mastery
  mistakes_min_sample:               5
  # curriculum coverage (NEW — closes the "only studied signs & parking" gap)
  gate_min_answers_per_topic:        5
  gate_required_topics: all_v1_topics      # every Topic in the v1 curriculum must be covered
  # advisory "exam ready" gate
  gate_last_n_mocks:                 3
  gate_required_passes:              2
  gate_major_topic_min:            0.70
  gate_min_unique_questions:       100
  # weights (sum = 1.0)
  weight_mock_performance:         0.40
  weight_topic_mastery:            0.30
  weight_mistake_recovery:         0.20
  weight_consistency_recency:      0.10
```

State resolution:
- `unique_questions_attempted < min_unique_questions_for_display` **or** zero mocks →
  `insufficient_data`.
- else if `mocks_completed < min_mocks_for_full` **or** `unique_questions_attempted <
  min_unique_questions_for_full` **or** curriculum coverage not met (below) → `initial`.
- else → `ready_estimate`.

"Unique questions attempted" = distinct `question_id` across answered `PracticeAnswer` +
`MockAnswer` (resolve `question_version_id` → `question_id`).

## Curriculum coverage (mandatory for "ready")

Define **coverage** as: for **every** `Topic` in `gate_required_topics` (all v1 topics), the
user has answered at least `gate_min_answers_per_topic` (5) questions in that topic. Coverage
is required for both the `ready_estimate` state and the "exam ready" badge. This guarantees a
user who has only drilled road signs and parking can **never** be labelled exam-ready or shown
a full readiness percentage.

If some topics are still under `gate_min_answers_per_topic`, the dashboard shows which topics
remain (e.g. `Qolgan mavzular: Chorrahalar, Temir yo'l kesishmalari`) instead of a readiness
percentage.

## Score

```
readiness_score = round(100 * (
    0.40 * mock_performance +
    0.30 * topic_mastery +
    0.20 * mistake_recovery +
    0.10 * consistency_recency
))
```

### 1. Mock performance (40%)
Most recent `recent_mock_count` (5) completed mocks within `recent_window_days` (30); each
`ratio = correct_count / question_count`; recency-weighted mean (newest highest). No mocks →
0 (already `insufficient_data`).

### 2. Topic mastery (30%)
Per topic within the window: `mastery_t = correct_t / answered_t`, counted only if
`answered_t >= topic_min_answers` (5). `topic_mastery = mean(mastery_t over counted topics)`.
The dashboard "weak topics" list uses `mastery_t` (lowest first); under-sampled topics are
shown as "needs more practice", but — per the coverage gate — the **badge/ready state require
those topics to reach the sample floor first**, so they are not silently ignored for
readiness.

### 3. Mistake recovery (20%)
`total = MistakeEntry count`, `resolved = resolved count`. If `total == 0` → neutral `1.0`.
Else `resolved / total`; low-confidence if `total < mistakes_min_sample` (5).

### 4. Consistency / recency (10%)
`active_days_7 = distinct local dates with ≥1 answer in last 7 days`;
`consistency = min(1, active_days_7 / 4)`; multiply by a recency factor (×0.5 if idle >3 days,
×0.25 if idle >7 days).

## Answer speed
Does **not** affect the score in v1 (avoids penalising careful users); average answer time is
shown as informational context only. Revisit in v2 if data shows speed predicts passing.

## Advisory "exam ready" gate

Badge appears only when **all** hold:
- `mocks_completed >= gate_last_n_mocks` (3), **and**
- ≥ `gate_required_passes` (2) of the last `gate_last_n_mocks` scored ≥ `minimum_correct`
  (18/20), **and**
- **curriculum coverage met** (every required topic ≥ `gate_min_answers_per_topic`), **and**
- no counted topic mastery below `gate_major_topic_min` (0.70), **and**
- `unique_questions_attempted >= gate_min_unique_questions` (100).

The gate is advisory; it never blocks starting a mock or practising.

## Implementation notes
Computed by a backend service from `PracticeAnswer`, `MockAttempt`/`MockAnswer`,
`MistakeEntry`; may be cached in `ReadinessSnapshot`
([02-domain-model.md](02-domain-model.md#ranking-readiness-see-dedicated-specs)) and recomputed
after each mock completion or on a schedule. All numbers come from the `readiness` config;
tuning them must not require code changes.
