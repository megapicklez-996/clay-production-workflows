# Plain-English Workflow Explainer

Use this reference when someone asks what a Clay Workflow does, how a record moves
through it, why a branch exists, what an approval controls, or whether the workflow
actually achieved its business outcome.

## Explanation contract

Explain the workflow at three distinct evidence layers:

1. **Intent** — node names, descriptions, prompts, and comments say what the builder
   meant the workflow to do.
2. **Enforcement** — code, conditions, schemas, tool mappings, trigger configuration,
   and approval checks define what the workflow can actually do.
3. **Proof** — run outputs and independent destination readbacks demonstrate what
   happened. A green graph or `completed` run is not proof of CRM, Audience, or
   sequencer success.

If the layers disagree, lead with the disagreement. Use `appears to`, `is configured
to`, or `was observed to` deliberately rather than blending them together.

## Story-first contract

Start with the simplest true version in two or three sentences. Then tell a connected
story about one representative account or person. The reader should be able to follow
the journey without translating a node inventory.

The narrative should have movement and causality:

- establish who or what enters and what job the workflow is trying to accomplish;
- explain why the next question is asked, not only that another node exists;
- describe meaningful yes/no branches and what each outcome protects;
- introduce external systems as actors with jobs, not a list of integrations;
- make the moment of paid work or external mutation feel consequential;
- resolve the story with the possible terminal outcomes and the proof still needed.
- name the exact fields and configured values that cause each meaningful branch.

Use connected paragraphs with sentences such as “Before it spends a credit…”, “If
Salesforce already knows this person…”, and “Only after those checks pass…”. Vary the
language to fit the actual evidence. Do not use a numbered phase list as the main
explanation. Node names, counts, and ledgers belong after the narrative as receipts.

## Field-level fidelity

Natural language must not erase the executable contract. When the graph exposes it,
include the exact:

- source field names and their fallbacks;
- normalized context keys;
- account size, country, industry, customer, opportunity, and readiness filters;
- title include terms, title exclude terms, locations, seniority floor, and result limit;
- CRM query fields and predicates;
- cache TTLs and accepted validation statuses;
- identity fields and equality rules;
- approval booleans, hashes, references, expirations, and destination IDs;
- copy cardinality, word limits, prohibited values, and required payload fields;
- suppression statuses, reply/bounce/unsubscribe indicators, and JIT lookup mappings;
- external tool input mappings and readback identifiers.

Use backticks for exact machine names and quote configured values. Pair each field with
its meaning: “`# Open Oppty` must equal zero, so companies with an active opportunity
stop here.” Do not dump every available provider parameter; include parameters actually
mapped by this workflow. Distinguish a field that exists in a tool schema from a field
the node actually maps.

Follow this causal spine when those stages exist:

```text
entry -> configuration and budget gate -> company/person eligibility
      -> cached identity and suppression checks -> paid enrichment if still needed
      -> generation -> deterministic validation -> one bounded repair -> independent QA
      -> payload preview -> separately approved external writes
      -> read-after-write verification -> terminal receipt
```

Do not force absent stages into the story. Describe branches as questions a human can
understand, such as “Do we already know this person?” or “Is external activation
approved?” Explain where the yes and no paths lead when the graph exposes them.

## Recommended narrative shape

1. **Opening:** what the workflow exists to accomplish and who enters.
2. **The journey:** connected prose from entry through qualification, enrichment,
   generation, approvals, writes, and verification.
3. **The tension:** the important stop paths, safety choices, or semantic conflict.
4. **The ending:** all legitimate terminal outcomes, including safe suppression.
5. **The reality check:** what is intended, what is executable, what has been observed,
   and the next proof needed.

These are story beats, not mandatory headings. Prefer a small number of evocative
headings over one heading per mechanical stage.

## Required sections

A durable explanation should answer:

- **What it is for:** the job and the unit of work: account, person, or queued contact.
- **What starts it:** each trigger and whether it is draft-safe, live, manual, or unknown.
- **What enters:** required identity and campaign configuration.
- **What happens:** the main journey in connected prose rather than a dump of nodes or
  a numbered phase summary.
- **What costs money:** paid enrichment, generation, or provider calls, plus any
  configured ceiling that could not be verified.
- **What changes other systems:** every Audience, CRM, sequencer, or queue write.
- **What can stop or suppress it:** approval, eligibility, missing identity, existing
  membership, unsubscribe, blocklist, validation, provider, or reconciliation gates.
- **How success is checked:** write receipts and independent readbacks.
- **What the evidence proves:** static structure, tested branches, observed outcomes,
  and remaining unknowns.

## Translation rules

Translate product jargon immediately:

- **Trigger:** the event that starts one workflow run.
- **Audience:** a saved group of accounts or people in Clay.
- **Enrichment:** looking up missing facts from Clay or an outside data provider.
- **Suppression:** deliberately preventing outreach because the person is unsafe,
  already satisfied, unsubscribed, replied, bounced, or blocklisted.
- **Idempotency:** a safeguard that makes a rerun avoid creating the same side effect
  twice.
- **Reconciliation/readback:** checking the destination after a write instead of
  trusting only the write request.
- **Canary:** a deliberately tiny live test before a larger launch.
- **Fail closed:** missing configuration or proof blocks the risky action while safe
  inspection remains possible.

Prefer “adds the person to the sending campaign” over “sequencer activation,” then
include the exact technical noun in parentheses when it helps the operator.

## Evidence and caveats

Never claim that a workflow:

- is live because it was published;
- succeeded because Clay marked the run `completed`;
- is safe because the graph validator passed;
- tested a draft edit through a trigger that follows the live graph;
- wrote to a destination without a destination receipt or readback;
- handles every branch when only the happy path was observed.

For each important claim, name the strongest available proof: node configuration,
structural validation, semantic audit, run output, or destination readback. If only
static evidence exists, say that the explanation describes configured behavior, not
observed production behavior.

## Audience levels

- **General:** describe the business journey and translate all specialist terms.
- **Executive:** emphasize purpose, risk gates, costs, external systems, and what is
  proven. Omit most node names.
- **Operator:** include human-readable node names, approval ownership, stop conditions,
  rerun behavior, and the next verification.
- **Technical:** add node types, contract boundaries, mappings, and semantic conflicts.

## Close

End with both lines:

```text
In one sentence: <record -> important gates -> external outcome -> verification>.
Next check: <the smallest exact evidence needed to resolve the biggest unknown>.
```
