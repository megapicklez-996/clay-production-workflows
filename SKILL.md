---
name: clay-production-workflows
description: Build, migrate, explain, audit, test, and launch-gate multi-node Clay Workflows that enrich accounts or people and may write to Audiences, a CRM, or a sequencer. Use for plain-English walkthroughs of production workflows, production hardening, parity migrations, reusable campaign templates, bounded canaries, semantic contract checks, cost and approval gates, payload completeness, idempotency, and downstream reconciliation. Do not use for simple table explanations, one-off enrichment questions, or read-only audience counts.
metadata:
  author: orchid-automation
  version: "0.4.0"
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

## Choose the operating mode

1. **Audit an existing workflow** — collect read-only evidence, validate the graph,
   run the semantic contract audit, inspect run outcomes, and issue a readiness
   ceiling. Read [semantic-contract-audit.md](references/semantic-contract-audit.md)
   and [failure-taxonomy.md](references/failure-taxonomy.md).
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

## Read-only evidence collection

Confirm the Clay workspace once with `clay whoami`. Share the workflow link and
human-readable name. Then prefer the bundled collector over repeated ad hoc commands:

```bash
python3 scripts/collect_workflow_evidence.py WORKFLOW_ID --output EVIDENCE_DIR
```

The collector only reads workflow metadata, graph, validation, diagram, snapshots,
triggers, and recent run metadata. It does not test, publish, resume, or mutate.

Audit the evidence:

```bash
python3 scripts/validate_contract.py EVIDENCE_DIR/graph.json \
  --validation EVIDENCE_DIR/validation.json
python3 scripts/summarize_runs.py EVIDENCE_DIR/runs.json \
  --failed-runs EVIDENCE_DIR/failed-runs.json
python3 scripts/audit_workflow.py EVIDENCE_DIR
```

Explain the workflow for a non-technical reader:

```bash
python3 scripts/explain_workflow.py EVIDENCE_DIR --audience general
```

Read [script-contracts.md](references/script-contracts.md) before modifying or
replacing these scripts. Structured data goes to stdout; diagnostics go to stderr.

## Canonical contract before graph work

Define one campaign manifest covering campaign identity, sources, eligibility,
required fields, exact sequence length, destinations, suppression, worst-case cost,
approval scope, terminal outcomes, and reconciliation ownership.

Start from [campaign-manifest.template.json](assets/campaign-manifest.template.json).
Defaults must permit no paid work and no external writes. Changing the normalized
manifest must invalidate prior approval.

## Production architecture

Prefer explicit stages: safe entry adapters; fail-closed preflight; deterministic
eligibility; cache-aware enrichment; durable per-person queueing; identity and
suppression; generation; deterministic validation; one repair and independent QA;
payload preview; separately approved writes; and read-after-write reconciliation.

Use deterministic code for routing, normalization, validation, hashing, budgets,
and identifiers. Use agents only for judgment or generation. Preserve exact values
with typed schemas or explicit tool input mappings.

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
independently read back. Static inspection can set a ceiling but cannot prove it.

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
