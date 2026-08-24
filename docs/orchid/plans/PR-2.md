# PR #2 governance repair plan

Source: `f96f519b5f1d265a4db05ecf0b7fa899380183cc`

## Objective

Close the two review findings that can incorrectly elevate a campaign to
`LIVE_READY`.

## Changes

1. Require the approvals implied by every configured external destination and
   require outbound activation approval for a `LIVE_READY` campaign.
2. Require non-empty external-write receipts and exact destination identifiers
   in verified readbacks before reconciliation can prove live readiness.
3. Add regression tests reproducing both rejected false-positive cases while
   preserving the existing valid fixture behavior.

## Owned paths

- `scripts/validate_manifest.py`
- `scripts/validate_reconciliation.py`
- `tests/test_scripts.py`

## Validation

- `python3 -m unittest discover -s tests -v`
- Positive strict manifest, graph-control, and reconciliation fixture checks
- `git diff --check`

## Boundaries

- Do not change unrelated heuristics, documentation, schemas, or fixtures.
- Do not merge or deploy.
