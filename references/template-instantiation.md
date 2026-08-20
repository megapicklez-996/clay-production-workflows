# Template Instantiation

1. Duplicate the template and preserve source workflow/snapshot identifiers.
2. Keep triggers on empty control segments while configuring.
3. Replace placeholders, destinations, owner, counts, and budgets.
4. Set state to `DRAFT` and all approvals false.
5. Normalize and hash the manifest.
6. Rebind account and person-queue sources; verify entity and count.
7. Resolve destinations through read-only lookups.
8. Run the semantic contract audit across every sequence consumer.
9. Update outdated agents and re-read persisted prompts/schemas.
10. Run a no-write preview before mutation approval.
11. Bind approval to final manifest hash, approver, timestamp, and expiry.
12. Follow the bounded ladder.

Changing sequence length requires updating generator, repair, validator, QA, payload,
destination variables, and receipts. A structurally valid, untested template is unproven.
