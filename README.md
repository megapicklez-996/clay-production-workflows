# Clay Production Workflows

An agent skill for building, migrating, explaining, auditing, testing, and
launch-gating production Clay Workflows.

It treats a workflow as a governed system rather than a diagram: exact field and
filter contracts, bounded spend, approval gates, idempotent writes, failure
classification, and downstream reconciliation all have to agree before a workflow
is called ready.

## Install with skills.sh

```bash
npx skills add orchidautomation/clay-production-workflows
```

Preview what the CLI discovers without installing:

```bash
npx skills add orchidautomation/clay-production-workflows --list
```

Install this skill explicitly:

```bash
npx skills add orchidautomation/clay-production-workflows \
  --skill clay-production-workflows
```

The repository keeps `SKILL.md` at its root, one of the standard discovery
locations supported by the skills CLI. Supporting scripts, references, assets,
evaluations, and tests travel with the skill.

## What it helps an agent do

- Explain a Clay workflow as a connected, plain-English story while preserving
  exact field names, operators, values, statuses, and payload mappings.
- Audit structural validity and semantic agreement across prompts, schemas,
  validators, repair steps, payload builders, and destination mappings.
- Design bounded canaries, explicit spend ceilings, approval scopes, suppression,
  idempotency, and read-after-write reconciliation.
- Classify partial and ambiguous failures without blindly repeating external writes.
- Instantiate reusable campaign templates without carrying stale approvals or
  destination identifiers into a new campaign.

## Offline tools

The scripts require Python 3.11 or newer. Fixture-based analysis is offline; only
live evidence collection requires an authenticated Clay CLI.

```bash
python3 scripts/validate_contract.py evals/fixtures/valid-production-workflow.json
python3 scripts/summarize_runs.py evals/fixtures/runs-mixed.json
python3 scripts/explain_workflow.py evals/fixtures/explainable-workflow.json
python3 -m unittest discover -s tests -v
```

See [`SKILL.md`](SKILL.md) for operating instructions and safety boundaries.

## Validation

```bash
npx skills add . --list
npx skills-ref validate .
python3 -m unittest discover -s tests -v
```

The fixtures are synthetic. This public repository does not include raw build
transcripts, live Clay workflow IDs, customer records, credentials, or message
bodies.

## License

MIT
