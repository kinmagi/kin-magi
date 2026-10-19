# Experiment 014 — Release reconciliation (separate proposed follow-on)

This is independent from Experiments 012 and 013 and does not launch Curious Worlds or publish scientific data. The existing historical files are unchanged.

## Failure addressed
In Experiment 012, READY is flushed before SQLite publication-row insertion. An interruption between these steps leaves a complete-looking package without a publication record. No real failure is demonstrated.

## Mechanism
Default inspect-only mode checks the exact package entries (and excludes symlinks), canonical manifest and receipt, manifest/READY hashes, independently verified catalog contents and catalog version, pinned candidate, archived source replay and human approval, publication eligibility, and conflicting or existing publication records.

- Incomplete package lacking READY: quarantined without modification.
- Valid package with matching row: consistent; no write.
- Valid READY package with absent row: eligible for an explicitly authorized, record-only insert in an SQLite IMMEDIATE transaction, rechecking state before insertion.
- Any other discrepancy: no repair.

Operator name and approval reference are required for repair. Record these in a separately controlled operator audit. No missing scientific approval is generated or waived; package files and earlier releases are never rewritten.

## Commands
Run from repository root:

```sh
python -m unittest discover -s experiment014 -p 'test_*.py' -v
python -m unittest discover -s experiment012 -p 'test_*.py' -v
python -m unittest discover -s experiment013 -p 'test_*.py' -v
python experiment014/reconcile.py /path/to/existing-stage.sqlite /path/to/releases cw012-example.1
# Only with deliberate separate human authorization:
python experiment014/reconcile.py /path/to/existing-stage.sqlite /path/to/releases cw012-example.1 --repair --operator 'operator name' --authorization 'change-ticket'
```

## Verification status and limitations
Eight added regression tests cover complete/repaired/incomplete packages and tampering scenarios. They have **not been executed in this session** because source checkout/network access was unavailable in the execution environment. No CI passing claim is made.

The initial prototype does not provide a tamper-resistant operator audit log, signatures/authenticated operator identities, or protection from malicious filesystem owners and concurrent external file rewrites. Approval metadata is inherited from Experiment 012 and is a trusted-operator declaration, not cryptographically authenticated. Catalog integrity checking detects disagreement rather than establishing scientific truth. Production deployment requires a further audit/security review and completed test run.
