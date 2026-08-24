# Testing and Launch

Use this reference for tests, backfills, publishing, or scale decisions.

## Draft versus live

- Plain/manual tests exercise the current draft.
- Audience-segment tests use the published/live graph after publish.
- Editing or restoring a draft does not publish it.
- Publishing changes the live graph; it does not prove the graph works.

## Bounded ladder

1. One synthetic or approved manual draft record.
2. One real no-write preview.
3. One fully approved end-to-end canary.
4. Two-to-five records covering materially different branches.
5. Ten-to-fifteen records with spend and success stop conditions.
6. Scale only after reconciliation.

State cohort, worst-case credits, BYOA ceiling, permitted/prohibited writes, stop
conditions, approval expiry, and reconciliation owner at each rung.

Before the live rung, verify the incident owner can execute the recorded trigger
pause method and that the rollback snapshot identifies a known-good draft. Restoring
that snapshot is not a live rollback by itself; the restored graph must be audited,
approved, and published.

Cover existing CRM contact, net-new contact, missing email, stale employer, existing
sequencer lead, suppressed/blocklisted lead, missing payload field, provider failure,
and duplicate rerun when those paths exist.

`completed` may mean no-send, suppressed, already satisfied, or review-only. It is
supporting evidence, never an activation-rate calculation.
