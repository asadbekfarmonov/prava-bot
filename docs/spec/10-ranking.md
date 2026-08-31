# 10 — Ranking

Rankings are a **v1 feature** (the owner wants them). They must reward **real preparation**,
not question farming. All points and aggregates are **computed server-side** from stored facts;
the client never submits points.

## Principles

- Do **not** rank primarily by raw number of questions answered.
- Reward: correct answers on **unique** questions, mistake recovery, **mock performance**, and
  **consistency** — with **daily caps** so grinding cannot dominate.
- No credit that can be farmed by repeating the easiest question.

## Points model (v1)

Points accrue to a server-side ledger and are aggregated per period.

```
Practice (per question):
  +1   first correct answer of a UNIQUE question (once per question, ever)
   0   incorrect
  +0   repeat correct of an already-credited question (no farming)
  (a small "review credit" may apply via mistake recovery below, not via repeats)

Mistake recovery:
  +2   a question in the mistakes queue answered correctly and thereby RESOLVED
       (once per resolution; re-missing then re-resolving does not re-award)

Mock exam (per completed mock, honest attempt):
  base: +1 per correct answer, credited at most once per mock
  pass bonus:
    18/20 → +10
    19/20 → +20
    20/20 → +35
  only one bonus (the highest reached) per mock; abandoned mocks award nothing

Daily consistency:
  +5   capped once per active day (an "active day" = met the daily goal or ≥10 answers)
```

### Daily cap

Total **practice** points are capped per day (config `ranking.daily_practice_cap`, e.g. 50)
so a marathon session cannot dominate the board. Mock and mistake-recovery points are not
capped by the practice cap but are naturally bounded (finite unique questions, one bonus per
mock). All caps live in ranking config (domain config, not env).

```yaml
ranking:
  practice_unique_correct: 1
  mistake_recovery: 2
  mock_correct: 1
  mock_bonus: { "18": 10, "19": 20, "20": 35 }
  daily_consistency: 5
  daily_practice_cap: 50
  min_answer_seconds: 2          # answers faster than this earn 0 (anti-bot)
  max_mock_bonus_per_day: 3      # only N mock bonuses count per day
```

## Ledger and aggregates (data)

```
UserPointsLedger
  id
  user_id            (index)
  source             enum(practice_unique, mistake_recovery, mock_correct, mock_bonus, daily_consistency)
  points             int
  ref_type           str        # e.g. "question", "mock_attempt", "mistake_entry", "day"
  ref_id             str
  local_date         date       # for daily caps + period aggregation
  created_at
  UNIQUE(user_id, source, ref_type, ref_id)   # idempotent: no double credit
```

Period leaderboards are aggregated from the ledger (materialized per day, then summed for
week/month/all-time), reusing SATStudy's daily/weekly stat pattern.

## Surfaces

Three ranges: **This week**, **This month**, **All time**.

```
Bu hafta:
1.  Ali        1,240
2.  Bekzod     1,180
3.  Madina     1,110
...
17. Siz          730
```

Always show the **user's own position** even when outside the visible top list. Views are
read-only, server-computed, paginated with a server max.

## Privacy

- The displayed name is the user-controlled **`ranking_name`** (defaults to `display_name`).
- Telegram **username is never shown** on rankings unless the user explicitly opts in.
- Users may **opt out** of public ranking (`show_on_ranking = false`) — they still see their
  own progress but do not appear on public boards.
- **Region/city ranking** is **not** in v1: we do not collect location. Only if region is
  later collected voluntarily and with consent would a regional board be considered (v2).

## Anti-cheat

All server-side:
- Points computed from stored `PracticeAnswer`/`MockAnswer`/`MistakeEntry`; client scores
  ignored (mass-assignment allowlist, [09-security.md](09-security.md)).
- **Unique-only** practice credit (ledger uniqueness) → repeating a question earns nothing.
- **min answer time** (`min_answer_seconds`) → impossibly fast answers earn 0 points and are
  flagged.
- **Rate limiting** + **duplicate-submission** protection (unique constraints) block rapid
  duplicate requests.
- **Mock farming** defenses: only completed, non-abandoned mocks award points; at most
  `max_mock_bonus_per_day` bonuses/day; abandoned/restarted mocks award nothing; the bonus is
  based on the server-graded `correct_count`.
- Daily caps bound total practice contribution.
- Ledger `UNIQUE(user_id, source, ref_type, ref_id)` makes crediting idempotent under retries
  and concurrent requests.

## Tests

- unique-correct credited once; repeats earn 0;
- mistake recovery awarded once per resolution;
- mock bonus matches server `correct_count`; abandoned mock awards nothing; daily bonus cap;
- daily practice cap enforced; sub-`min_answer_seconds` answers earn 0;
- client-submitted points ignored; concurrent duplicate requests don't double-credit;
- own-position shown outside top list; opted-out user absent from public board but sees self.
