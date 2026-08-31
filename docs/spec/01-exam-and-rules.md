# 01 — Exam and rules

All facts here are sourced from
[`research/uzbekistan-driving-license.md`](../../research/uzbekistan-driving-license.md)
(last verified **2026-08-31**). That research is the upstream source; when it changes,
reconcile this file **and** the exam configuration (below) in the same change.

## Theoretical exam format (official, verified)

- **20** electronic test questions per exam.
- Questions may be **static or animated**.
- Each question has **2–5 answer choices**; **exactly one** is correct.
- **One global 25-minute timer** for all 20 questions (not per-question). The exam ends
  automatically when time expires.
- Result is scored automatically; afterwards the system shows the result, which answers
  were right/wrong, and time spent.

### Pass rule

| Category | Correct required | Max mistakes |
| --- | ---: | ---: |
| B (and other normal categories) | **18 / 20** | 2 |
| A1 | 16 / 20 | 4 |

v1 targets **category B → pass at ≥18/20.** The pass threshold is a per-category value in
the exam configuration, not a hard-coded literal, so A1/others can be added later.

### Exam-mode restrictions (mirrored in our mock)

During the mock there must be **no** help: no study materials, no explanations, no hints,
no correct-answer reveal until submission or time expiry. This mirrors the official rule
that the exam assesses independent knowledge.

## How questions are chosen — our app vs. the real exam

These two statements must be kept distinct in all copy and docs:

- **Our application** (verified true of *us*): we maintain **one shared published question
  bank**. When a user starts a mock, our app selects **20 random, unique, published
  questions** for that user's category and language, **without replacement**, and snapshots
  them to the attempt. Practice questions and mock questions are the **same `Question`
  records** — there is no separate exam bank.
- **The real Uzbekistan exam** (state only what is verified): the automated system forms a
  **20-question exam from approved theory questions**. We do **not** claim the official
  system uses our practice bank, nor any specific random-selection algorithm, nor any fixed
  per-topic distribution — none of that is confirmed by an official source.

There is **no fixed topic quota / exam blueprint**. Official guidance does not define a
per-topic distribution, so neither our mock nor our copy asserts one. Topic tags exist for
**learning organisation only**.

## Exam configuration — single source of truth

Legal exam rules are **domain configuration**, not deployment configuration. They live in
**one** versioned place in the backend (e.g. `app/domain/exam_config.py`), optionally
mirrored to a read-only `exam_config` table for auditability. They are **never** stored in
environment variables and **never** duplicated in Markdown-as-authority, mock templates
(removed), or scattered literals. This document describes them; the backend module is the
authority the code reads.

Each configuration has a **`version`**. A `MockAttempt` **snapshots** the applicable values
at start (see [02-domain-model.md](02-domain-model.md)) so in-progress and historical
attempts stay interpretable if the rules later change.

Category B, exam config **v1**:

```yaml
exam_config:
  version: 1
  category: B
  last_verified: 2026-08-31
  questions: 20
  time_limit_seconds: 1500        # 25 minutes, single global timer
  minimum_correct: 18             # pass threshold
  maximum_mistakes: 2
  answer_options_min: 2
  answer_options_max: 5
  correct_options_per_question: 1
  result_validity_months: 2       # informational (process), not enforced in v1
# Reserved for later categories (not implemented in v1):
# A1: { questions: 20, minimum_correct: 16, maximum_mistakes: 4, ... }
```

Readiness thresholds are also domain configuration and live alongside the exam config; see
[07-readiness.md](07-readiness.md).

## Categories and eligibility (context)

| Category | Min age | Vehicle |
| --- | ---: | --- |
| A | 16 | motorcycles |
| B | 18 | passenger vehicles ≤ 3,500 kg, ≤ 8 passenger seats |
| C | 18 | vehicles > 3,500 kg |
| D | 21 | passenger vehicles > 8 seats |

## 2026 reforms relevant to the product

- From **1 Feb 2026**: category A and B applicants **no longer must complete the theory
  part** of driver training at an auto-school — theory may be self-studied. Practical
  training remains mandatory.
- New **A1** subcategory from **1 Jan 2026** with independent preparation and a lower theory
  threshold (16/20).

## Process facts (informational; feeds a v2 exam-guide, not built in v1)

- Medical certificate: form **083/h**, entered into the electronic system.
- Exam order is mandatory: **theory first, then practical**; failing theory blocks practical.
- A passing **theory result is valid for 2 months** while attempting the practical.
- Retakes: theory from the **next working day**; practical after **≥7 calendar days**.
- National licence validity: **10 years**.

## Out-of-scope caveats (from research)

- The **practical exam** specification (exercise list, penalty-point matrix, e.g. the
  "≤99 penalty points" figure documented for one automated centre) is **not verified
  nationwide** and is **out of v1 scope**.
- First-aid content must be built from current Uzbekistan rules and recognised first-aid
  guidance — **not** invented from old question banks.
