# Script Contracts

- Non-interactive; flags only; concise `--help`.
- JSON to stdout; diagnostics to stderr.
- Exit `2` invalid input, `3` missing dependency, `4` auth/access, `5` Clay command,
  `6` filesystem, and `10` strict audit blockers.
- Collector commands are read-only: never test, publish, update triggers, resume, or mutate.
- Evidence bundles carry `evidence_contract_version`; reject incompatible required
  JSON shapes rather than silently treating absent fields as empty evidence.
- Raw data goes to an explicit directory; stdout stays compact.
- Fixture analysis works offline.
- Add unit tests whenever parsing or severity logic changes.
