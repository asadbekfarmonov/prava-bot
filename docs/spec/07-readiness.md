# 07 — Readiness score

Readiness answers "how likely is this user to pass the real theory exam?" It must **not**
show a confident high percentage after only a handful of questions. All thresholds and
weights below are **domain configuration** (alongside the exam config in
[01-exam-and-rules.md](01-exam-and-rules.md)) — **not** environment variables.

## Display states

Readiness resolves to one of three labelled states:

1. **`insufficient_data`** — not enough evidence to estimate. Show
   `Ma'lumot yetarli emas` ("Not enough data"). No percentage, no "exam ready" badge.
2. **`initial`** — some data, but below the "full" bar. Show a percentage labelled as an
   **initial** estimate: `Boshlang'ich daraja: 63%` ("Initial level: 63%"). No "exam ready"
   badge.
3. **`ready_estimate`** — enough data for a real readiness percentage. Show
   `Imtihonga tayyorlik: 81%`. The **"exam ready"** badge appears only if the advisory gate
   (below) is also satisfied.

### Data thresholds (config)

```yaml
readiness:
  # state gating
  min_unique_questions_for_display: 40     # below this => insufficient_data
  min_unique_questions_for_full:   100     # and mocks below min => stay "initial"
  min_mocks_for_full:                3     # >= this (with coverage) => ready_estimate
  # component windows / samples
  recent_mock_count:                 5     # most recent N mocks considered
  recent_window_days:               30     # mocks/answers older than this are down-weighted
  topic_min_answers:                 5     # a topic needs >= this to count toward mastery
  mistakes_min_sample:               5     # below this, recovery is low-confidence
  # advisory "exam ready" gate
  gate_last_n_mocks:                 3
  gate_required_passes:              2     # >= this of the last N at >= minimum_correct
  gate_major_topic_min:            0.70    # no counted topic below this
  gate_min_unique_questions:       100
  # component weights (must sum to 1.0)
  weight_mock_performance:         0.40
  weight_topic_mastery:            0.30
  weight_mistake_recovery:         0.20
  weight_consistency_recency:      0.10
```

Resolution logic:

- `unique_questions_attempted < min_unique_questions_for_display` **or** zero mocks
  → `insufficient_data`.
- else if `mocks_completed < min_mocks_for_full` **or**
  `unique_questions_attempted < min_unique_questions_for_full` → `initial`.
- else → `ready_estimate`.

"Unique questions attempted" counts distinct `question_id` across `PracticeAnswer` +
`MockAnswer` (answered).

## Score

```
readiness_score = round(100 * (
    0.40 * mock_performance +
    0.30 * topic_mastery +
    0.20 * mistake_recovery +
    0.10 * consistency_recency
))
```

Each component is in `[0, 1]`. In the `initial` state the same formula is used but the
result is labelled "initial" (the caller does not hide the number, only frames it).

### 1. Mock performance (40%)

- Consider the **most recent `recent_mock_count` (5)** completed mocks within
  `recent_window_days` (30). If fewer exist, use what exists.
- For each considered mock: `ratio = correct_count / question_count`.
- Weight more recent mocks higher (linear recency weights, newest highest).
- `mock_performance = weighted_mean(ratios)`.
- If **no** completed mocks: `mock_performance` is treated as **0** for the score, but this
  case is already `insufficient_data`, so a bare number is not shown.

### 2. Topic mastery (30%)

- For each `Topic`, over answers within `recent_window_days`:
  `mastery_t = correct_t / answered_t`, counted **only** if `answered_t >= topic_min_answers`
  (5). Topics below the sample floor are **excluded** (unknown, not zero).
- `topic_mastery = mean(mastery_t over counted topics)`.
- If **no** topic meets the floor, `topic_mastery = 0` for the score (again typically
  `insufficient_data`).
- The dashboard's "weak topics" list uses these `mastery_t` values (lowest first), marking
  under-sampled topics as "needs more practice" rather than a low score.

### 3. Mistake recovery (20%)

- Let `total = count(MistakeEntry for user)`, `resolved = count(resolved = true)`.
- If `total == 0`: **neutral** — set `mistake_recovery = 1.0` (no outstanding mistakes is not
  a penalty). This is safe because the state gate still requires real coverage before a
  "ready_estimate".
- Else `mistake_recovery = resolved / total`. If `total < mistakes_min_sample` (5), the
  component is **low-confidence**; it still contributes but the state stays `initial` if the
  other gates are unmet.

### 4. Consistency / recency (10%)

- `active_days_7 = distinct local dates with >=1 answer in the last 7 days`.
- `consistency = min(1, active_days_7 / 4)` (target 4 active days/week).
- `recency_penalty`: if the user has not answered in the last 3 days, multiply
  `consistency` by 0.5; if not in the last 7 days, by 0.25.
- `consistency_recency = consistency * recency_penalty_factor`.

## Answer speed

Answer speed does **not** affect the readiness **score** in v1 (keeps the model simple and
avoids penalising careful users). Average answer time **is** displayed as informational
context on the mock result and dashboard. Revisit in v2 if data shows speed predicts passing.

## Coverage / confidence

Coverage is handled by the **state gate** (unique-question thresholds) rather than a
continuous multiplier, so the behaviour is predictable and easy to explain. A user cannot
reach `ready_estimate` (or the badge) without `gate_min_unique_questions` unique questions
attempted, preventing a high score from a tiny memorised sample.

## Advisory "exam ready" gate

Shown as a badge only when **all** hold (config keys in parentheses):

- `mocks_completed >= gate_last_n_mocks` (3) **and**
- at least `gate_required_passes` (2) of the last `gate_last_n_mocks` (3) mocks scored
  `>= minimum_correct` (18/20), **and**
- no counted topic mastery below `gate_major_topic_min` (0.70), **and**
- `unique_questions_attempted >= gate_min_unique_questions` (100).

The gate is advisory guidance to the user; it never blocks starting a mock or practising.

## Implementation notes

- Readiness is computed by a backend service from `PracticeAnswer`, `MockAttempt`/
  `MockAnswer`, and `MistakeEntry`. It may be cached in `ReadinessSnapshot`
  ([02-domain-model.md](02-domain-model.md#readiness-computed-optional-snapshot)) and
  recomputed after each mock completion or on a schedule.
- All numbers above come from the `readiness` config block; changing them must not require a
  code change beyond the config value.
