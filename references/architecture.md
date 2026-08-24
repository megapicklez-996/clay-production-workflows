# Governed Workflow Architecture

Use this reference when building a new Clay Workflow or migrating an existing table
or workbook for parity.

## Stage contract

| Stage | Responsibility | Proof before proceeding |
|---|---|---|
| Entry adapter | Normalize Audience, manual, webhook, or queue input | Canonical entity and source receipt |
| Preflight | Bind manifest, approvals, destinations, counts, and budgets | Config hash, source verification, readiness state |
| Eligibility | Apply deterministic account/person rules | Verdict and reason |
| Enrichment | Use cached values first, then approved paid paths | Provider, cost, value, and validation state |
| Person queue | Create durable, independent person work items | Expected count, idempotency key, queue receipt |
| Suppression | Detect existing or unsafe downstream state | Lookup status and reason |
| Generation | Produce only the fields defined by the copy contract | Typed output matching sequence length |
| Validation | Check deterministic rules, then bounded repair and QA | Violations, retry count, QA verdict |
| Preview | Assemble the exact destination payload | Missing-field list and destination match |
| Mutation | Perform one separately approved external write | Write response and approval reference |
| Reconciliation | Read the destination and classify the outcome | Verified identifiers and terminal receipt |

## Design invariants

- One campaign manifest is the only campaign-specific edit surface.
- Safe templates point at empty control segments and placeholder destinations.
- Entry adapters normalize; the manifest decides eligibility.
- Paid tools come after deterministic filters and cache checks.
- Multiple contacts become durable per-person records when independent retries,
  receipts, or activation are required.
- Every external mutation has a preceding gate and a following readback.
- Every branch reaches a named terminal outcome; no-send is explicit.
- Context passed to AI is compact, signed, and distinct from the operational receipt.
- Production ownership, kill-switch controls, rollback evidence, and retention are
  part of the contract rather than launch-day notes.

## Parity matrix

Compare sources and eligibility, enrichment providers and fallbacks, required fields,
copy behavior, Audience writes, CRM stewardship, sequencer behavior, costs, failures,
and reconciliation. Visual similarity or one happy-path record is not parity.
