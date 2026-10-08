# Curious Worlds — Experiment 013

Repeated scientific acquisition and verification, extending unchanged Experiments 010–012. All new writes use a **fresh Experiment 013 staging database**. Historical catalogues, world/laboratory databases and 012 staging are never migrated.

Python 3.10+; standard library only. Keep the four experiment directories as siblings. Run inside `experiment013`:

```bash
python run_tests013.py --out /tmp/cw013-tests.json
python offline_demo.py --out /tmp/cw013-offline
python live_demo.py --allow-live --include-mp --out /tmp/cw013-live
```

Output paths must be new. Tests use isolated temporary databases. The offline demonstration makes no external requests. The live demonstration runs **two finite rounds** by default, at most three if explicitly requested. It forces fresh HTTP retrieval rather than counting cached results as repeated live evidence. It writes exact response evidence into its new `staging.sqlite` and exports `live_results.json`. A false `verified_repeated_live_acquisition` means the objective was not demonstrated; process completion alone is not a successful live result.

**Delivered results:** all 120 tests pass (11 + 25 + 41 + 43); 11 offline demonstration checks pass. Live NIST and PubChem calls reached the configured proxy but were denied by its destination policy; Materials Project had no credential and made no request. Consequently, repeated real-source acquisition remains unverified. No successful live response, real correction or real source conflict is claimed. See `REPORT.md`, `test_results.json`, `offline_results.json` and `live_results.json`.

## Staging and monitoring

```bash
python cli013.py --stage /tmp/cw013-staging.sqlite acquire nist
python cli013.py --stage /tmp/cw013-staging.sqlite acquire pubchem --query '{"cid":962}'
python cli013.py --stage /tmp/cw013-staging.sqlite monitor
python cli013.py --stage /tmp/cw013-staging.sqlite verify
python cli013.py --stage /tmp/cw013-staging.sqlite recover
```

The inherited connectors use official NIST CODATA bulk text, PubChem PUG REST and the Materials Project summary API. Initial coverage remains two finite kg constants, one explicitly selected compound's molecular descriptor, and one explicitly selected crystal's computed density. No unrestricted search, scraping or extrapolation is added.

Materials Project requires `MP_API_KEY` from the environment and `{"material_id":"mp-149","terms_accepted":true}` after actual terms review. The opt-in live demonstration includes MP only with `--include-mp`; it declares terms review only if `CW_MP_TERMS_ACCEPTED=yes`. Neither flag grants access or creates a credential. Never put keys into queries, arguments, SQLite or files submitted to GitHub. Do not disable proxy or TLS verification to work around denied hosts.

Monitoring reports completed/unfinished runs, per-source success/failure counts, real HTTP successes, latest error, staged identity/property coverage, pending review keys, observations and exact-response evidence metadata. HTTP `Date` means response date; `Last-Modified` means resource metadata, **not an experimental measurement date**. Missing timestamps, uncertainties, experimental conditions and publication details remain unknown. Formula equality is insufficient to equate bulk materials or crystal phases.

NIST constants are labelled `reference_constant` in monitoring, retaining Experiment 012's original `measured`/`exact` field for compatibility. PubChem molecular weight and MP crystal density are `computed_property`. None of these connectors supplies a new direct experimental measurement. Staged coverage is not authoritative scientific coverage.

## Repeated observations and integrity

Every acquisition gets an immutable start and terminal result. HTTP exchanges retain exact bounded response bytes, status, acquisition time, selected safe response headers, body SHA-256 and a metadata digest. Parsed observations retain unchanged source units, conditions, uncertainty, publication/version/rights metadata and capture origin. Independent validation re-parses archived captures and compares the complete record.

Comparison uses the **latest** accepted matching record. Equal normalized scientific content is `unchanged`; different content from a newer ordered CODATA release is a `correction` candidate requiring review; older versions, same-version differences, returns to earlier values and undated changed PubChem snapshot hashes are `conflict`. Metadata-only changes are retained and flagged separately. No difference is averaged or automatically preferred. A changed hash alone does not establish scientific correction.

Successful/failed HTTP exchanges survive parsing failure or interruption. Observations and the terminal result commit atomically. `recover` marks only expired unfinished runs interrupted, preserves their evidence, and leaves re-acquisition to a new run. An immutable response cache origin prevents simulated bytes being reused as live evidence. Injected test transports must label their evidence synthetic.

The CLI contains no approval or publication command. Existing 012 candidate/explicit-review functionality is retained through the module interface, with its independent source replay and licensing gates. No acquisition, monitoring or scheduler code calls approval or publication. Synthetic fixtures cannot be approved. Existing objects retain their original dataset version/digest; no migration or "latest" pointer is created.

## Explicit scheduling only

```bash
python cli013.py --stage /path/to/new-staging.sqlite schedule --name daily-nist --source nist --interval 86400
python cli013.py --stage /path/to/new-staging.sqlite tick --allow-live --limit 1
```

`schedule` stores a job without starting it. `tick` requires `--allow-live` and processes a bounded number of due jobs (default three, maximum ten). Five-minute leases survive restart; unique tokens fence stale worker completions after reclamation. No unattended service or recurring external requests are installed. Only configure cron/systemd after separate explicit authorisation.

Transport reserves one request/second per source across connections sharing the staging file, limits bodies to 2 MB, uses a 15-second socket timeout, allows at most three attempts and checks a 120-second budget before requests/waits. It respects numeric/HTTP-date `Retry-After`, persists cooldowns, defers waits over 60 seconds, and records PubChem red/black throttling cooldown. Authentication/policy/permission denials are not repeatedly retried. Ordinary timeouts/transient server failures have bounded retry. Cached reads are not live HTTP successes. Separate staging files/deployments do not coordinate rate limits.

See `schema.sql` for the **additional** 013 tables; the inherited 012 schema is created first. `baseline_blobs.json` pins all historical tracked files to the reviewed GitHub baseline. Generated databases and environments are excluded from the PR; the demos reproduce databases locally.
