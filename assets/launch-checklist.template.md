# Clay Workflow Launch Checklist

## Configuration

- [ ] No placeholders or `REPLACE_ME` values remain.
- [ ] Manifest hash matches the approval manifest.
- [ ] Approval is scoped, unexpired, and names an owner.
- [ ] Source and destination IDs were verified read-only.
- [ ] Trigger entity types and segment counts are correct.
- [ ] Only one intended trigger generation is active; old and new cohorts do not overlap unexpectedly.
- [ ] Every custom Clay function fingerprint matches the approved manifest.

## Contract

- [ ] Generator, repair, validator, QA, payload, and receipt agree on sequence length.
- [ ] All required destination fields are present on every eligible branch.
- [ ] Tool input mappings and result paths were read back after save.
- [ ] Conditional calls, transition registries, targets, and edge handles agree.
- [ ] Context required after a tool node is supplied through explicit input references.
- [ ] Required fields are checked at the final payload boundary.

## Safety

- [ ] Worst-case credits and BYOA cost are approved.
- [ ] Existing-record, reply, bounce, unsubscribe, and blocklist behavior is defined.
- [ ] A just-in-time suppression check runs before sequencer enrollment.
- [ ] Mutations use separate approval gates and fill-only writes where appropriate.
- [ ] Ambiguous write failures require readback before retry.

## Evidence

- [ ] Manual draft test passed.
- [ ] No-write preview passed.
- [ ] Real canary reached every intended destination.
- [ ] Audience, CRM, campaign membership, and sequencer readbacks passed.
- [ ] Duplicate rerun did not duplicate or re-enroll the record.
- [ ] Terminal outcome distribution is reported without treating `completed` as success.
- [ ] No later node downgrades a verified write or activation to false.
- [ ] No run contains incompatible terminal outcome classes.

## Release

- [ ] Published graph is the graph that passed the canary.
- [ ] Live triggers are intentionally bound and paused/resumed as intended.
- [ ] Stop conditions and reconciliation owner are recorded.
- [ ] Business, builder, approver, reconciliation, and incident owners are named.
- [ ] Trigger pause method and known-good rollback snapshot are recorded.
- [ ] Downstream remediation owner understands that graph rollback does not undo writes.
- [ ] Log allowlist, redactions, and evidence/raw-payload retention are recorded.
- [ ] Evidence/CLI compatibility check passed.
