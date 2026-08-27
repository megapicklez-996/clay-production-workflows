# Design Provenance

Maintainer-only source record. Do not load for ordinary workflow work.

## Operational evidence

- Private build transcripts covering parity, bounded credits, Audiences, CRM and
  sequencer writes, missing payload fields, multi-contact flow, and launch gates.
- One finished production workflow and its reusable template, inspected read-only.
- Observed failures including provider HTML/non-JSON responses and sequencer
  blocklist rejection.
- A production audit that exposed a unified-trigger cutover regression, circular
  approval binding, context loss after a destination write, contradictory terminal
  outcomes, label-based write/readback false positives, and a mutable custom
  function outside the workflow snapshot.

No raw transcripts, live workflow identifiers, credentials, private lead values,
customer names, or message bodies are bundled.

## Skill-design sources

- https://agentskills.io/specification
- https://agentskills.io/skill-creation/best-practices
- https://agentskills.io/skill-creation/optimizing-descriptions
- https://agentskills.io/skill-creation/evaluating-skills
- https://agentskills.io/skill-creation/using-scripts
