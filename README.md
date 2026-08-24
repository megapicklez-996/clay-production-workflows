# Clay Production Workflows

Most Clay workflows are easy to demo and hard to operate.

A graph can validate while still sending the wrong records, spending more credits
than expected, producing a two-email sequence for a five-email campaign, or writing
to Salesforce and Instantly without proving either write landed.

This skill gives an agent a production methodology for finding those gaps. It can
explain an existing workflow in plain English, audit the real configuration, harden
a build, test it with a bounded canary, and decide whether it is actually ready to
launch.

## The workflow it helps you build

Imagine one account entering a campaign.

The account should not move forward because a node is called “Qualified.” The
workflow needs to inspect the actual fields. In the synthetic example bundled with
this repo, `Campaign Launch Ready` and `Qualified Company` must both be true,
`# of Employees` must be between `250` and `5000`, `Domain` must exist,
`# Open Oppty` must equal `0`, and any truthy value in `Active Customer`
stops the account. `Country` must match an allowed value and `Industry` must
contain an approved term.

Before paid enrichment begins, the workflow calculates its worst-case Clay spend:

```text
expected_account_count × (
  projected_fixed_credits_per_company
  + people_per_company × projected_credits_per_person
)
```

That projected amount must fit inside `approved_total_clay_credits`. The approval
must match the current configuration hash, so changing a filter, destination, or
campaign contract invalidates stale approval.

Each eligible account becomes one or more durable person work items. Person-level
filters then use exact title include terms, title exclude terms, seniority, location,
identity, suppression, and cache freshness. Missing data can be enriched, but a
successful enrichment node is not enough. Required values such as the normalized
LinkedIn URL or email must exist in the final payload.

Copy generation follows a contract too. If the campaign requires five emails, the
generator, validator, repair step, QA step, payload builder, Instantly mapping, and
reconciliation receipt must all agree on five subjects and five bodies. One layer
saying “five” cannot rescue another layer that still maps two.

Only then can separately approved writes reach Clay Audiences, Salesforce, or
Instantly. After each write, the workflow reads the destination back. A Clay run
marked `completed` is not treated as business success until the intended record,
campaign membership, and sequencer state are independently verified.

That full journey is what this skill means by a production workflow.

## What you can ask an agent

Once installed, try requests like:

```text
Explain this Clay workflow as a story for a non-technical operator. Preserve the
exact field names, filter operators, configured values, approval gates, and writes.
```

```text
Audit this Clay workflow for launch readiness. Check semantic contracts, spend
ceilings, suppression, idempotency, payload completeness, and downstream readbacks.
Do not mutate or run anything.
```

```text
Turn this working Clay campaign into a reusable template. Identify every source,
destination ID, filter value, cache TTL, copy requirement, and approval that must
be rebound or invalidated.
```

```text
Design a bounded canary for this workflow. Start with one no-write preview, define
the exact stop conditions, and tell me what evidence is required before scaling.
```

The skill deliberately separates:

- what node names and descriptions claim;
- what executable configuration actually enforces;
- what run evidence and destination readbacks prove happened.

## Use it with the Clay plugin

The Clay plugin and this skill serve different layers of the same job. The plugin
routes work across Audiences, Search, Routines, Tables, and Workflows and provides
the current CLI mechanics for reading data, discovering actions, editing graphs,
testing, publishing, and snapshots. This skill adds the production contract around
a multi-node Workflow: approval binding, semantic consistency, bounded canaries,
idempotency, terminal outcomes, and destination reconciliation.

Use the plugin alone for ordinary Audience questions, net-new searches, routine
runs, and table diagnosis. Add this skill when a Workflow can spend materially,
write to another system, activate outreach, run unattended, or scale. See
[`clay-plugin-integration.md`](references/clay-plugin-integration.md) for the full
responsibility split and handoff sequence.

## Install

Install with the [skills CLI](https://skills.sh):

```bash
npx skills add orchidautomation/clay-production-workflows
```

See what will be installed first:

```bash
npx skills add orchidautomation/clay-production-workflows --list
```

Install only this skill for Codex:

```bash
npx skills add orchidautomation/clay-production-workflows \
  --skill clay-production-workflows \
  --agent codex
```

The repository keeps `SKILL.md` at its root, so the skills CLI discovers the
skill directly and installs its scripts, references, assets, evaluations, and tests
together.

## What the agent returns

Depending on the request, the agent should produce one or more of these artifacts:

- A connected plain-English story following one record from entry to terminal
  outcome.
- An exact inventory of fields, normalized keys, allowed values, include and
  exclude terms, comparison operators, accepted statuses, TTLs, and tool mappings.
- A structural and semantic audit with blockers separated from warnings.
- A readiness verdict of `DRAFT_BLOCKED`, `PREVIEW_READY`, `CANARY_READY`,
  or `LIVE_READY`.
- A bounded test ladder with credit limits, record limits, stop conditions, and
  approval scope.
- A reconciliation plan showing how every external write will be read back.
- A reusable campaign manifest or parity matrix for a migration or template.

`LIVE_READY` has a deliberately high bar. It requires a real canary that reached
every intended destination and was independently read back. Static graph inspection
cannot prove it.

## Audit a live workflow

The offline scripts require Python 3.11 or newer. Live evidence collection also
requires the Clay CLI supplied by the Clay plugin, an authenticated workspace, and
network access.

Confirm the active workspace:

```bash
clay whoami
```

Collect a read-only evidence bundle:

```bash
python3 scripts/collect_workflow_evidence.py WORKFLOW_ID \
  --output .clay-evidence/WORKFLOW_ID
```

The collector reads workflow metadata, graph, validation, diagram, snapshots,
triggers, and recent run metadata. It does not publish, test, resume, or mutate the
workflow.

Run the audit:

```bash
python3 scripts/validate_contract.py .clay-evidence/WORKFLOW_ID/graph.json \
  --validation .clay-evidence/WORKFLOW_ID/validation.json

python3 scripts/summarize_runs.py .clay-evidence/WORKFLOW_ID/runs.json \
  --failed-runs .clay-evidence/WORKFLOW_ID/failed-runs.json

python3 scripts/audit_workflow.py .clay-evidence/WORKFLOW_ID
```

Generate the story-first explanation:

```bash
python3 scripts/explain_workflow.py \
  .clay-evidence/WORKFLOW_ID \
  --audience general > workflow-explanation.md
```

Review [the script contracts](references/script-contracts.md) before modifying the
tools or depending on their structured output.

## Try it without Clay

Everything below runs against synthetic fixtures:

```bash
python3 scripts/validate_contract.py \
  evals/fixtures/valid-production-workflow.json

python3 scripts/summarize_runs.py \
  evals/fixtures/runs-mixed.json

python3 scripts/explain_workflow.py \
  evals/fixtures/explainable-workflow.json \
  > /tmp/clay-workflow-explanation.md

python3 -m unittest discover -s tests -v
```

The explainer fixture includes concrete account filters, title rules, cache TTLs,
copy constraints, approval fields, destination mappings, and failure paths. It is a
safe way to see the expected level of detail.

## What is inside

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Routing, operating modes, safety boundaries, and the production methodology |
| `scripts/` | Read-only evidence collection, contract validation, run classification, auditing, and explanation |
| `references/` | Architecture, testing, reconciliation, failure handling, template instantiation, and explainer guidance |
| `assets/` | Campaign manifest, audit report, launch checklist, parity matrix, reconciliation schema, and explainer templates |
| `evals/` | Trigger queries, synthetic workflow fixtures, failures, and expected results |
| `tests/` | Offline unit tests for the bundled tools |

Start with [`SKILL.md`](SKILL.md). For the complete workflow model, read
[`architecture.md`](references/architecture.md). For human-readable walkthroughs,
read [`plain-english-explainer.md`](references/plain-english-explainer.md).

## Safety boundaries

Installing the skill does not authorize external actions.

The agent must get explicit approval before it runs paid enrichments, publishes or
resumes a workflow, executes a canary, backfills records, or writes to Clay
Audiences, a CRM, or a sequencer. Audit and explanation requests remain read-only.

The recommended progression is:

1. One manual draft record.
2. One no-write payload preview.
3. One explicitly approved canary.
4. Two to five records covering important branches.
5. A bounded cohort with a credit ceiling and stop condition.
6. Scale only after destination readbacks agree.

External mutations are never retried blindly. The agent first determines whether
the original write landed.

## Validate the package

```bash
npx skills add . --list
npx skills-ref validate .
python3 -m unittest discover -s tests -v
```

GitHub Actions runs all three checks on every push and pull request.

All fixtures are synthetic. This public repository does not contain raw build
transcripts, live Clay workflow IDs, customer records, credentials, or message
bodies.

## License

MIT
