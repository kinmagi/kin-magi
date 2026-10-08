# Experiment 012 — Scientific methodology and results

Experiment 012 implements a bounded acquisition/review pipeline, not a general scientific knowledge system or physical simulation. It builds on repository main commit `4995d0b5a8256d7d4631925ea31ce036881f2e51`. Experiments 010 and 011 are imported unchanged; their 24 tracked file blobs are compared against upstream in `baseline_blobs.json`. No older experiment, existing world state, catalogue, or material object is written by this experiment. The PR contains only additions under `experiment012/` and excludes generated SQLite files, environments and secrets.

## Method and data flow

Official connector → bounded transport/cache → archived capture → typed incoming observation → validation/change report → explicitly selected candidate → separate human approval → new immutable release package.

The staging schema is in `schema.sql`: `responses` caches bounded GETs; immutable `captures` retains source evidence; `attempts` records sanitized transport outcomes; immutable `incoming` records stores observations and their baseline-specific classification; immutable `candidates` stores complete manifests and selected records; append-only `approvals`/`publications` bind review to content; `jobs`/`throttle` preserve scheduling and request timing. JSON payloads retain scientific conditions, uncertainty and provenance without flattening away source context. The authoritative normalized catalogue schema remains Experiment 011's unchanged schema.

Validation checks explicit identities, a narrow dimensional registry, positive finite supported values, uncertainty units/classifications, positive ordered condition ranges, official endpoint origin, source release/snapshot hash, retrieval evidence and rights metadata. Unsupported properties fail closed. Staging and candidate construction are separate from physical proposals/state changes. No calculation or physical transition is introduced, so conservation-law enforcement remains in the unchanged 010/011 engine and ledger. Their regression tests and demo audit replay still pass.

Change detection normalizes supported units and compares scientific content separately from retrieval time. It detects idempotent repeats, duplicates, newly covered identities, incompatible records, and same-source/version changes requiring correction review. A changed version is a *candidate* correction, not proof that a new value is scientifically preferable. Conflicts are never averaged or silently resolved. Compound/crystal namespaces remain distinct: equal formulas are insufficient to equate phases, polymorphs or laboratory materials. Metadata-only observations remain retained duplicates rather than causing arbitrary replacement.

A candidate contains the old complete manifest plus selected mapped constants, a new version, old manifest digest, source evidence and documented resolutions. Every selected record must match independently re-parsed archived bytes. Explicit approval names a reviewer, stores approval evidence and declares licence review. Publication verifies the hash/manifest/evidence again, creates a new directory exclusively, builds and verifies a new read-only catalogue, flushes files and writes `READY` last. No publication is performed for the delivered candidate. Temporary unit-test releases test that code path and are discarded.

## Sources and scientific classifications

| Connector | Initial scope | Scientific interpretation | Limits |
|---|---|---|---|
| NIST SRD 121 official CODATA bulk text | Electron mass and atomic mass constant | CODATA recommended evaluated constants; `measured` category distinguishes these from exact definitions, not a claim of a new direct experiment | Only finite kg values; uncertainty is CODATA standard uncertainty; current terms reviewed before publication |
| PubChem PUG REST | Explicit CID, molecular formula and molecular weight | Computed molecular descriptor, `calculated` | No measured bulk properties, uncertainty or publication in this endpoint; contributor rights unresolved; staging only |
| Materials Project summary API | Explicit material ID, formula, density, origins and update/version metadata | Computed crystal density, `calculated`; absent value `unknown` | Requires credential and accepted terms; no calibrated ambient T/P validity or reported measurement uncertainty; staging only |

References reviewed on 2026-10-08:

- [NIST CODATA bulk table](https://physics.nist.gov/cuu/Constants/Table/allascii.txt), [reference background](https://physics.nist.gov/cuu/Constants/), and [NIST licensing](https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications). SRD has distinct copyright/licensing treatment; the non-SRD reuse statement is not assumed to cover SRD 121.
- [PubChem PUG REST](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest) and [downloads/licensing guidance](https://pubchem.ncbi.nlm.nih.gov/docs/downloads). PubChem requests must stay below five/second; this implementation uses one/second and honors server cooldown. Contributor licences are not inferred from government hosting.
- [Materials Project API documentation](https://docs.materialsproject.org/downloading-data/using-the-api/getting-started) and [official AWS registry pointing to terms](https://registry.opendata.aws/materials-project/). The registry links [terms](https://materialsproject.org/about/terms), which returned 403 during review. Terms acceptance is therefore not asserted by this work and MP is not acquired live.

Missing source uncertainty, publication details or conditions remain explicit unknown fields. This system does not invent those values, extrapolate unknown conditions, substitute estimated values as measurements, or infer a licence grant. The initial connectors do not cover broad thermal, electrical, pressure-dependent or temperature-dependent datasets. Fits and illustrative physics in earlier experiments remain labelled as before.

## Demonstration

The old authoritative manifest is `cw011-2026-10-08.1`, digest `5595729dd86d2f8e80a4c4c6c23021f8fe1f1d1f8b29302cc5fde230dfb5f906`.

The source-backed NIST excerpt adds electron mass to local catalogue coverage and detects the already present atomic mass constant as a duplicate. This is a genuine **coverage update**, not a claimed historical correction to CODATA. Simulated correction/conflict tests are labelled synthetic and cannot publish. The candidate is `cw012-demo-coverage.1`, recorded in `candidate_demo.json`; it remains non-authoritative.

Eight end-to-end checks pass: update detection, duplicate detection, candidate validation, rejection of publication without approval, byte-identical old catalogue, byte-identical world, byte-identical laboratory, and object recovery after reopening. Existing objects retain their old dataset version/digest and audit history. Demo paths are new and exclusive; no existing user databases are involved.

## Automated verification and access limits

`test_results.json` records 11 Experiment 010 tests, 25 Experiment 011 tests and 41 new Experiment 012 tests: 77 total, all passing. Tests exercise source traceability, identity, units, missing/unsupported values, provenance/conditions/uncertainty, normalized duplicates, synthetic conflicts/corrections, immutable staging captures/candidates, unsubstantiated-value rejection, source replay, approval/licence gates, temporary approved release creation, old-release preservation, restart recovery, reference/state isolation, caching, corruption detection, sanitized credential handling, retries, dynamic throttling, schedules and lease recovery.

Direct permitted live requests were attempted through the configured proxy. Both NIST and PubChem were unavailable due to destination denial (initial attempts reported tunnel 403); Materials Project had no `MP_API_KEY` and made no request. `live_results.json` explicitly reports `all_live_passed: false`. The browser could retrieve the official NIST table, permitting a transparent transcribed excerpt; this is **not** a successful automated live connector test. PubChem/MP tests use synthetic response fixtures, not recorded real API data. The work cannot claim full live integration validation until access is available.

## Operational limitations and next experiment

Format validation and byte replay establish provenance consistency, not experimental accuracy or expert scientific endorsement. The approval workflow assumes trusted local operators; it supplies no authenticated accounts, cryptographic signatures or adversarial database protection. Release files use read-only permissions and hash checking, which filesystem owners can override. Interrupted releases without `READY` stay quarantined for manual inspection; a crash after `READY` but before the staging publication log requires receipt/log reconciliation. No automatic migration or cleanup overwrites release files.

Rate coordination covers workers sharing one staging file, not separate deployments. Five-minute job leases exceed the transport's bounded request/retry duration under normal operation; a paused process or unusual OS stall could outlive a lease. Scheduling is a CLI tick intended for cron/systemd; no continuously running service is installed. There is no broad source discovery crawl: initial discovery means explicit curated endpoint/identity selection. No agents, university/account systems, paywall bypass or internet scraper are present.

Recommended Experiment 013: enable permitted official endpoints, obtain and review MP credentials/terms, capture genuine PubChem/MP responses, validate each connector against live schemas, and add an independently reviewed material identity/phase mapping and source-specific licensing decisions. Exercise a real published-source correction using two archived official releases, preserve both, and pilot signed reviewer receipts and interrupted-publication reconciliation before running unattended acquisition in production.
