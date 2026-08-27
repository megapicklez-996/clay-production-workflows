# Semantic Contract Audit

Use this reference for audits, template reviews, and before every publish.

Clay's graph validator checks structural wiring. It can pass while prompts, schemas,
validators, and payloads disagree. One reviewed template required five emails in its
manifest and validator while its generation, repair, and QA agents handled only two.

## Procedure

1. Extract manifest cardinalities, required fields, destinations, readiness, and approvals.
2. Enumerate every producer and consumer of those fields.
3. Compare names, prompts, schemas, deterministic code, repair, QA, payload mappings, and receipts.
4. Report both sides of each mismatch and the first unsafe effect.
5. Run `scripts/validate_contract.py`, then inspect fields it marks unknown.
6. Run `scripts/validate_graph_controls.py` with the manifest to check exact
   destination payload requirements, write-to-readback reachability, idempotency,
   suppression, and terminal leaves. Treat unavailable mappings or edges as unknown,
   not as a pass.
7. Run `scripts/validate_snapshot_semantics.py` against the current raw snapshot to
   compare transition calls, configured registries, edge handles, entrypoints, and
   pinned context after tool nodes.
8. Run `scripts/validate_trigger_safety.py` and `scripts/analyze_run_traces.py` to
   detect overlapping trigger generations and terminal outcomes that contradict a
   previously proven side effect.

## Checks

- Sequence length and numbered subject/body fields agree everywhere.
- Required destination fields are produced on every eligible branch.
- Output paths use the real tool result shape.
- Tool mappings reference persisted inputs, not invented variables.
- Source and destination IDs match approved values.
- Approval references match and bind to the current config hash.
- Workflow code does not populate its own `approved_config_hash` or approval
  reference from the current unapproved configuration.
- Called conditional transitions, configured transition IDs and targets, and edge
  handles agree exactly; initial adapters do not also receive routed work.
- Retry count is bounded and preserves original context.
- QA examines exactly what will be sent and returns verdicts, not rewritten copy.
- Readbacks verify the same object and campaign the write targeted.
- A code node that parses a write response is not counted as an independent
  readback; the graph must contain a separate read-only destination action.
- Custom Clay functions are fingerprinted, bound in the manifest, and audited for
  hidden paid work and mutations.
- Unified and legacy trigger cohorts do not overlap unless only one generation is
  proven active.
- A later node never downgrades an already verified write or activation to false or
  reclassifies it as a pre-activation stop.
- Node names do not describe stale behavior that conflicts with prompts or schemas.
- Every approved destination has an inspectable write mapping containing its manifest
  payload fields and a downstream readback.
- Every graph leaf records one recognized terminal outcome.

## Severity

- **BLOCKER**: could spend, write, or send with wrong configuration or incomplete payload.
- **HIGH**: prevents a required path, hides business failure, or breaks reconciliation.
- **MEDIUM**: weakens observability, maintainability, or safe scaling.
- **LOW**: stale naming or hygiene without current execution impact.

Any outbound sequence-cardinality mismatch is a blocker.
