# 01 — Exam and rules

All facts here are sourced from
[`research/uzbekistan-driving-license.md`](../../research/uzbekistan-driving-license.md)
(last verified **2026-08-31**). Treat that document as the upstream source; when it
changes, reconcile this file and the app's exam constants.

## Theoretical exam format (official)

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

v1 targets **category B → pass at ≥18/20.** The pass threshold must be a per-category
constant, not hard-coded to 18, so A1/others can be added later.

### Timing guidance

25 min / 20 questions = **~75 seconds/question** on average. The product should train users
to answer familiar questions well under 75s to leave time for harder situational questions.
The mock uses a **single countdown**, mirroring the real exam.

### Exam-mode restrictions (mirror in the mock)

During the mock there must be **no** help: no study materials, no explanations, no hints,
no correct-answer reveal until submission or time expiry. This mirrors the official rule
that the exam assesses independent knowledge.

## Categories and eligibility (context)

| Category | Min age | Vehicle |
| --- | ---: | --- |
| A | 16 | motorcycles |
| B | 18 | passenger vehicles ≤ 3,500 kg, ≤ 8 passenger seats |
| C | 18 | vehicles > 3,500 kg |
| D | 21 | passenger vehicles > 8 seats |

## 2026 reforms relevant to the product

- From **1 Feb 2026**: category A and B applicants **no longer must complete the theory
  part** of driver training at an auto-school — theory may be self-studied (online or
  independently). Practical training remains mandatory.
- New **A1** subcategory from **1 Jan 2026** with independent-preparation allowance and a
  lower theory threshold (16/20).

## Process facts (for a future exam-guide feature — v2, informational only)

- Medical certificate: form **083/h**, entered into the electronic system.
- Exam order is mandatory: **theory first, then practical**. Failing theory blocks practical.
- A passing **theory result is valid for 2 months** while attempting the practical.
- Retakes: theory from the **next working day**; practical after **≥7 calendar days**.
- National licence validity: **10 years**.

These are **not** implemented in v1 features; recorded so the exam-day checklist (v2) can
be built accurately.

## Exam constants (machine-readable)

These become backend configuration / a category config table. Do not scatter literals.

```yaml
country: UZ
last_verified: 2026-08-31
category_B:
  minimum_age: 18
  theory_self_study_allowed: true
  practical_training_mandatory: true
  medical_certificate: "083/h"
  theory_exam:
    questions: 20
    total_time_seconds: 1500          # 25 minutes, single global timer
    answer_options_min: 2
    answer_options_max: 5
    correct_options_per_question: 1
    minimum_correct: 18
    maximum_mistakes: 2
    result_validity_months: 2
  licence_validity_years: 10
# For later categories (not implemented in v1):
category_A1:
  theory_exam:
    questions: 20
    minimum_correct: 16
    maximum_mistakes: 4
```

## Important product caveats (from research)

- Official guidance does **not** publish a fixed per-topic question distribution. The mock
  must **not** claim "N sign questions, M intersection questions" per exam. Topic tags are
  for **learning organisation**, not a promised exam blueprint.
- The **practical exam** specification (exercise list, penalty-point matrix, e.g. the
  "≤99 penalty points" figure documented for one automated centre) is **not verified
  nationwide** and is **out of v1 scope**.
- First-aid content must be built from current Uzbekistan rules and recognised first-aid
  guidance — **not** invented from old question banks.
