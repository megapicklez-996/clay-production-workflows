---
name: clay-production-workflows
description: Build, migrate, explain, visualize, audit, test, and launch-gate multi-node Clay Workflows that enrich accounts or people and may write to Audiences, a CRM, or a sequencer. Use for plain-English walkthroughs and in-conversation visualizations of governed workflow diagrams, production hardening, parity migrations, reusable campaign templates, bounded canaries, semantic contract checks, cost and approval gates, payload completeness, idempotency, and downstream reconciliation. Do not use for simple table explanations, one-off enrichment questions, generic non-Clay diagrams, or read-only audience counts.
license: MIT
compatibility: Python 3.11+ for offline checks; authenticated Clay CLI and network access for live evidence collection.
metadata:
  author: orchid-automation
  version: "0.7.0"
---

# Clay Production Workflows

Treat a Clay Workflow as a governed production system, not merely a valid graph.
The target outcome is a workflow whose configuration, contracts, test evidence,
external writes, and readbacks agree.

## Requirements

The offline scripts require Python 3.11+. Live evidence collection additionally
requires the Clay CLI supplied by the Clay plugin, authenticated workspace access,
and network access. Fixture analysis and semantic checks work without Clay access.

## Boundaries

- Use this skill for Clay **Workflows** or a table-driven flow being moved into a
  governed Workflow.
- For explaining an existing Clay table DAG, use the Clay table-analysis workflow.
- For ordinary Audience counts or filters, use the Clay Audiences workflow.
- Never run paid enrichments, tests, backfills, publish, resume triggers, or write
  to Audiences, CRM, or a sequencer without the user's explicit approval for that
  action and scope.
- A request to audit or design does not authorize mutation.

## Pair with the Clay plugin

When the Clay plugin is available, use its `clay` entry-point skill to select the
right product surface and its focused skills for live mechanics. This skill does
not replace those instructions: it adds production contracts, approvals, evidence,
and launch criteria around multi-node Workflows.

For builds and edits, use the plugin's workflow skills to discover current actions
and schemas, mutate the graph, validate structure, inspect runs, manage snapshots,
and distinguish draft from published behavior. Apply this skill before graph work
to define the canonical contract, during the build to preserve its invariants, and
afterward to audit semantics, bound testing, reconcile writes, and issue readiness.

Read [clay-plugin-integration.md](references/clay-plugin-integration.md) when routing
a mixed Clay request, combining plugin skills during a production Workflow task, or
deciding which layer owns a check. If the plugin is absent, keep using offline
fixtures and semantic checks; do not invent live CLI shapes or claim workspace proof.

## Choose the operating mode

1. **Audit an existing workflow** — collect read-only evidence, validate the graph,
   run the semantic contract audit, inspect run outcomes, and issue a readiness
   ceiling. Read [semantic-contract-audit.md](references/semantic-contract-audit.md)
   and [failure-taxonomy.md](references/failure-taxonomy.md). When launch or live
   operation is in scope, also read [operations-and-data.md](references/operations-and-data.md).
2. **Build or migrate for parity** — define the canonical contract, stage the
   architecture, add fail-closed controls, and prove parity with bounded evidence.
   Read [architecture.md](references/architecture.md).
3. **Instantiate a reusable template** — replace the campaign manifest, rebind safe
   sources and destinations, invalidate stale approvals, and test all contract
   consumers. Read [template-instantiation.md](references/template-instantiation.md).
4. **Test or launch-gate** — use the bounded ladder, distinguish draft from live,
   reconcile every write, and report a readiness verdict. Read
   [testing-and-launch.md](references/testing-and-launch.md) and
   [reconciliation.md](references/reconciliation.md).
5. **Explain in plain English** — turn the graph and available run evidence into a
   noob-friendly operating story without mistaking labels for enforced behavior.
   Read [plain-english-explainer.md](references/plain-english-explainer.md).
6. **Visualize a supplied workflow diagram** — turn a Mermaid flowchart for a Clay
   production workflow into a faithful in-conversation visual without dropping
   gates, stop paths, stage boundaries, or evidence caveats. Read
   [workflow-visualization.md](references/workflow-visualization.md).

## Read-only evidence collection

Confirm the Clay workspace once with `clay whoami`. Share the workflow link and
human-readable name. Then prefer the bundled collector over repeated ad hoc commands:

```bash
python3 scripts/collect_workflow_evidence.py WORKFLOW_ID --output EVIDENCE_DIR \
  --manifest campaign-manifest.json --receipts reconciliation-receipts.json \
  --trace-run BOUNDED_CANARY_RUN_ID
```

The collector only reads workflow metadata, graph, validation, the current raw
snapshot, triggers, redacted Audience cohort fingerprints, custom-function
fingerprints, and recent run metadata. `--trace-run` adds an allowlisted outcome
trace without emails, message bodies, or raw provider payloads. It does not test,
publish, resume, or mutate.

Audit the evidence:

```bash
python3 scripts/validate_contract.py EVIDENCE_DIR/graph.json \
  --validation EVIDENCE_DIR/validation.json
python3 scripts/validate_manifest.py EVIDENCE_DIR/manifest.json
python3 scripts/validate_graph_controls.py EVIDENCE_DIR/graph.json \
  --manifest EVIDENCE_DIR/manifest.json \
  --function-fingerprints EVIDENCE_DIR/function-fingerprints.json
python3 scripts/validate_snapshot_semantics.py EVIDENCE_DIR/current-snapshot.json
python3 scripts/validate_trigger_safety.py EVIDENCE_DIR/triggers.json \
  --audience-segments EVIDENCE_DIR/audience-segments.json
python3 scripts/analyze_run_traces.py EVIDENCE_DIR/run-traces.json
python3 scripts/check_evidence_compat.py EVIDENCE_DIR
python3 scripts/validate_reconciliation.py EVIDENCE_DIR/receipts.json \
  --manifest EVIDENCE_DIR/manifest.json
python3 scripts/summarize_runs.py EVIDENCE_DIR/runs.json \
  --failed-runs EVIDENCE_DIR/failed-runs.json --graph EVIDENCE_DIR/graph.json
python3 scripts/audit_workflow.py EVIDENCE_DIR
```

Explain the workflow for a non-technical reader:

```bash
python3 scripts/explain_workflow.py EVIDENCE_DIR --audience general
```

When the user supplies Mermaid and asks to see the workflow as a visualization in
the conversation, treat the Mermaid as the source diagram and follow
[workflow-visualization.md](references/workflow-visualization.md). Use the host's
native in-conversation visualization capability when it is available. Do not turn
that request into a standalone website or silently return the same Mermaid source.

Read [script-contracts.md](references/script-contracts.md) before modifying or
replacing these scripts. Structured data goes to stdout; diagnostics go to stderr.

## Canonical contract before graph work

Define one campaign manifest covering campaign identity, sources, eligibility,
required fields, exact sequence length, destinations, suppression, worst-case cost,
approval scope, payload fields by destination, terminal outcomes, accountable owners,
kill-switch and rollback details, data handling, reconciliation ownership, and the
fingerprints of mutable custom Clay functions.

Start from [campaign-manifest.template.json](assets/campaign-manifest.template.json).
Defaults must permit no paid work and no external writes. Changing the normalized
manifest must invalidate prior approval.

The normalized configuration excludes the `approvals` object so approval evidence
does not create a circular hash. Use the hash reported by
`scripts/validate_manifest.py`; never hand-edit or approximate it. A production
claim requires named business, build, approval, reconciliation, and incident owners.

## Production architecture

Prefer explicit stages: safe entry adapters; fail-closed preflight; deterministic
eligibility; cache-aware enrichment; durable per-person queueing; identity and
suppression; generation; deterministic validation; one repair and independent QA;
payload preview; separately approved writes; and read-after-write reconciliation.

Use deterministic code for routing, normalization, validation, hashing, budgets,
and identifiers. Use agents only for judgment or generation. Preserve exact values
with typed schemas or explicit tool input mappings.

Treat a write response as an attempt receipt, not a readback. A readback requires a
separate read-only destination action after the mutation, exact identity matching,
and equality checks for the fields the workflow claims to have written.

## Mandatory semantic audit

Clay graph validation is necessary but not sufficient. Compare the canonical
contract across node names, prompts, input/output schemas, validators, repair
agents, QA agents, payload builders, destination mappings, and receipts.

For a sequence of length `N`, every consumer must produce, validate, map, and
reconcile exactly `N` subjects and bodies. A structural pass cannot override a
semantic mismatch. Treat an untested template as unproven even when it validates.

## Identity, idempotency, and suppression

- Validate actual required values, not just successful node statuses.
- Prefer normalized LinkedIn URL for a person and normalized domain for an account,
  with CRM IDs when already known.
- Derive per-person idempotency from campaign identity plus stable person identity.
- Use fill-only updates unless overwriting was explicitly approved.
- Check campaign membership, replies, bounces, unsubscribes, unsafe statuses, and
  blocklist evidence when available.
- Repeat suppression immediately before sequencer enrollment to reduce race windows.

## Testing and readiness

Progress through one manual draft record, one no-write preview, one approved canary,
two-to-five branch-covering records, then a bounded cohort with a stop condition.
Scale only after destination readbacks are verified.

Do not equate Clay `completed` with business success. Classify terminal outcomes as
activated and verified, already satisfied, review-only, safely suppressed, provider
failure, destination rejection, or reconciliation failure.

Use only `DRAFT_BLOCKED`, `PREVIEW_READY`, `CANARY_READY`, or `LIVE_READY`.
`LIVE_READY` requires a real canary that reached every intended destination and was
independently read back, plus an outcome trace with no side-effect downgrade or
contradictory terminal classification. Static inspection can set a ceiling but
cannot prove it.

Before live operation, record the exact trigger pause method, rollback snapshot,
downstream remediation owner, permitted log fields, redactions, and retention. A
snapshot restore changes the draft only; it is not a live rollback until the
restored graph is re-audited, approved, and published. See
[operations-and-data.md](references/operations-and-data.md).

## Failure handling

Recognize non-JSON/HTML provider responses, rate limits, timeouts, blocklists,
validation errors, stale destination IDs, missing credentials, and partial writes.
Do not blindly retry an external mutation. First determine whether it landed.
If Clay terminates before reconciliation, report side-effect uncertainty and the
exact readback required. See [failure-taxonomy.md](references/failure-taxonomy.md).

## Report

Use [workflow-audit-report.template.md](assets/workflow-audit-report.template.md).
Include the workflow link, compact graph, structural and semantic findings, trigger
safety, test evidence, outcome limits, costs and approvals, downstream readbacks,
readiness verdict, and exact remaining actions. Summarize evidence; do not dump raw
graphs, private records, credentials, or message bodies.

When the user asks what the workflow does, write a connected story before any
inventory, table, or checklist. Give the record a concrete role in the narrative and
walk it from entry to terminal outcome using transitions that explain why each stage
exists. Do not substitute numbered phase summaries for prose. Separate three evidence layers:
what node labels and descriptions say is intended, what executable configuration
enforces, and what runs plus destination readbacks prove happened. Define unfamiliar
Clay and GTM terms at first use. Name paid steps, approval gates, external writes,
suppression paths, failure paths, and what remains unknown. Start from
[workflow-explainer.template.md](assets/workflow-explainer.template.md) when a durable
explanation artifact is useful.

Do not paraphrase an executable filter as merely “checks fit,” “checks eligibility,”
or “checks safety.” Preserve the exact field names, normalized keys, configured values,
include/exclude terms, comparison operators, accepted statuses, tool mappings, and
payload requirements that make the branch pass or fail. Put field names in backticks
and explain their business meaning in the same paragraph.

## Provenance

The non-obvious rules come from real Clay build transcripts, a finished production
workflow, its reusable template, and observed failures. Read
[design-provenance.md](references/design-provenance.md) only when maintaining the
skill or evaluating whether a rule is still justified.
