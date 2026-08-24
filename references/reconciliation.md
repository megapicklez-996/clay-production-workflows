# Reconciliation Contract

Each terminal receipt should preserve workflow and campaign IDs, config and AI hashes,
stable identity, the campaign-plus-identity idempotency key, eligibility and suppression
decisions, provider/cost path, approvals, intended destination, external response IDs,
side-effect certainty, readback evidence, terminal outcome, stop reason, and owner.
Start from `assets/reconciliation-envelope.schema.json`.

| Write | Required readback |
|---|---|
| Audience upsert | Lookup by stable identity; verify selected fields and no blank regression |
| CRM account/contact update | Lookup returned ID and verify intended fields |
| CRM campaign membership | Lookup exact contact plus campaign pair |
| Sequencer enrollment | Lookup exact email plus campaign and verify required variables |

An API success response is not a readback. Use only: `activated_verified`,
`already_satisfied`, `review_only`, `safely_suppressed`, `provider_failure`,
`destination_rejection`, or `reconciliation_failure`.

Run `scripts/validate_reconciliation.py` over one receipt or `{ "data": [...] }`.
Two distinct activated receipts for the same idempotency key are a blocker. A timeout
after submission with no resolving readback remains `submitted_unknown`; reconcile
the destination before retrying.
