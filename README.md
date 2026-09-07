# prava-bot

Research and implementation workspace for the Uzbekistan driving-license assistant.


## Locked v1 decisions / principles

- **Two-level roles (admin / user).** There are exactly two levels. Any Telegram id in
  `ADMIN_TELEGRAM_IDS` (the `SUPERADMIN_TELEGRAM_IDS` alias is folded in) is a full
  **ADMIN**, resolved server-side on every request; everyone else is a **USER**. There
  is no persisted role tier, no superadmin/reviewer/author distinction, and no
  role-assignment endpoint. The `users.admin_role` DB column is vestigial (kept for
  schema stability) and is never consulted for authorization.
- **Question authoring is `save = live`.** Creating or editing a question via the admin
  API publishes it immediately — there are no draft → submit → review → publish steps in
  the UI. The only blocking gate is a **minimal quality floor**:
  1. 2–5 answer options,
  2. exactly one correct option,
  3. a non-empty uz prompt **or** an attached media object (and, if media is set, the
     object must exist in storage).
  Per-option explanations, the short "Eslab qoling" note, and a linked YHQ rule are
  **encouraged but optional** (surfaced as non-blocking hints), never a publish blocker.
- **Integrity guarantees are unchanged.** Immutable published versions + version pinning
  (an edit forks a new version; historical attempts keep rendering the pinned old
  version), no answer-leak during live mocks, server-authoritative timer/grading,
  `needs_reverification` propagation on rule supersede, and audit events all remain in
  force. Bulk import still lands rows as DRAFT (never auto-publishes). Seed ingestion is
  unchanged.
