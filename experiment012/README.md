# Curious Worlds — Experiment 012

A small scientific acquisition pipeline extending the unchanged Experiment 011 catalogue builder and read-only provider. Acquisition and scheduling write **only a separate staging SQLite database**. Creating a candidate does not publish it or change existing laboratory objects.

Python 3.10+; standard library only. Keep `experiment010`, `experiment011` and `experiment012` as sibling directories in the repository. Run commands inside `experiment012`.

```bash
python run_tests.py --out /tmp/cw012-tests.json
python demo.py --out /tmp/cw012-demo
python live_check.py --out /tmp/cw012-live.json
```

All output paths must be new. The demo builds fresh temporary world, lab, previous catalogue and staging databases; detects newly acquired electron-mass coverage plus a duplicate; validates a candidate; rejects unapproved publication; restarts and verifies the previous catalogue and objects. It never operates on your existing world databases. See `demo_results.json`, `test_results.json`, `live_results.json`, `REPORT.md`, and `fixtures/README.md`.

## Acquisition and review

```bash
python cli.py --stage /tmp/cw012-staging.sqlite acquire nist --refresh
python cli.py --stage /tmp/cw012-staging.sqlite acquire pubchem --query '{"cid":962}'
python cli.py --stage /tmp/cw012-staging.sqlite review
python cli.py --stage /tmp/cw012-staging.sqlite candidate --ids 1 --version cw012-example.1
```

Use the IDs reported by **your** staging review, not assumed IDs from the example. Corrections/conflicts need explicit resolution notes via `--resolutions '{"ID":"review justification"}'`. Candidate selection is deliberately limited to mapped NIST kg constants. PubChem and Materials Project records can be staged/reviewed, but cannot enter an 011 release until scientifically justified identity/property mappings and source-rights review are implemented.

The NIST connector retrieves the official CODATA bulk text and extracts two finite constants. PubChem retrieves one CID's computed molecular formula/weight using PUG REST. Materials Project queries one material's computed density via the official summary endpoint, requiring `MP_API_KEY` in the environment and `{"material_id":"mp-149","terms_accepted":true}` after actual terms review. No credentials go in CLI queries, SQLite, fixtures or GitHub. `CW_MP_TERMS_ACCEPTED=yes` allows the opt-in live checker to declare that review. No account creation, key provisioning or authentication bypass is included.

Missing uncertainty, publication or T/P validity is reported as unavailable, not fabricated. PubChem contributor licensing remains unresolved. Computed crystal density does not establish laboratory density at arbitrary temperature/pressure. No general scientific model, chemistry solver or autonomous agent is added.

## Publication requires separate explicit approval

Review the candidate hash, complete source captures, references, scientific classification, conditions, changes, rights and resolution notes. A human then supplies approval evidence in a text file. These commands describe the operator workflow; **the delivered demo candidate has not been approved**.

```bash
python cli.py --stage /tmp/cw012-staging.sqlite approve CANDIDATE_HASH \
  --reviewer 'Reviewer name' --evidence-file /path/to/approval.txt --licenses-reviewed
python cli.py --stage /tmp/cw012-staging.sqlite publish CANDIDATE_HASH --releases /path/to/new/releases
```

Approval binds the exact candidate digest. Publication revalidates the manifest and independently re-parses archived captures. Synthetic fixtures and unresolved rights cannot be approved. Release construction creates a new version directory exclusively, validates its catalogue, writes approval receipt and finally a `READY` marker after fsync. Existing versions are never opened for writing. Do not consume a directory without `READY`; retain and inspect interrupted directories. There is no mutable "latest" pointer. Objects stay pinned to their old dataset version/digest; migration requires a future explicitly reviewed operation.

Approval is a declared human action in a trusted local process, not authenticated identity or a cryptographic signature. Filesystem administrators can change files; catalogue content checks detect tampering when reopened. Restrict staging/release filesystem access in deployment.

## Scheduling and recovery

```bash
python cli.py --stage /path/to/staging.sqlite schedule --name daily-nist --source nist --interval 86400
python cli.py --stage /path/to/staging.sqlite tick
```

Invoke `tick` from cron/systemd (for example once every five minutes). It processes at most ten due jobs per invocation with durable five-minute leases, crash recovery, bounded retries and re-acquisition idempotency. Schedule a small explicit CID/material ID, not global searches. Jobs only acquire/stage; they never approve or publish. Failures retry on a later tick; there is no daemon installed by this project.

Transport allows only connector endpoints, forbids redirects, verifies normal TLS, limits each response to 2 MB, uses a 25-second timeout and at most three attempts, caches with a one-hour default TTL, throttles each source to one request/second shared within one staging database, respects `Retry-After`, and persists cooldown for red/black PubChem throttling signals. A single scheduler/staging file should coordinate each source; separate databases/hosts are not globally coordinated. Do not run independent workers that cumulatively exceed provider limits.

## Extension interface

Add an explicitly allowlisted connector implementing `fetch(transport, query, refresh)` and `parse(body, evidence)`; register property dimensions, scientific identity and conditions. Store exact captures and immutable incoming observations. Add fixture tests, permitted live tests, source-specific rights policy, and a separately reviewed catalogue export mapping. Do not reinterpret unknown values or let a language model supply reference numbers.
