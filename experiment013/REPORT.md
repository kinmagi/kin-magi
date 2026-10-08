# Experiment 013 — Scientific limitations and verification report

## Result

Implemented monitored repeated acquisition, exact evidence retention, latest-observation change detection, explicit scheduled ticks, interruption recovery, and finite opt-in live checks in a new directory. All 120 automated tests and 11 offline demonstration checks pass. **Successful repeated live scientific acquisition has not been demonstrated:** the managed proxy denies NIST/PubChem destinations and no Materials Project credential is available. This is a partial fulfilment of the live scientific objective, not a claim of production-ready source integration.

Repository baseline: main commit `c1f33789a9b85c25149c88f0d4537dda2a488ab5`. Experiment 012 connectors, transport, scheduler, schema, independent validation, candidate construction and publication gates were inspected before implementation. All 50 historical tracked file blobs (repository README plus Experiments 010–012) match upstream before and after regression tests. The PR adds only `experiment013/`; no historical source, result, database or object is modified. Existing 005–009 uploads and project files are not touched.

## Scientific method

The unchanged 012 adapters retain official endpoint allowlists and a narrow typed record schema. A new transport archives exact response bytes and safe HTTP metadata; a new staging wrapper independently validates/re-parses captures before recording observations; monitoring exposes acquisition and validation outcomes separately from scientific review. The authoritative manifest remains Experiment 011's `cw011-2026-10-08.1` with digest `5595729dd86d2f8e80a4c4c6c23021f8fe1f1d1f8b29302cc5fde230dfb5f906`. Experiment 012's demonstration candidate was not authoritative and is not promoted here.

No new scientific numbers are inserted into a catalogue. The offline demonstration replays the existing transparently transcribed NIST excerpt, then uses explicitly synthetic protocol variations to exercise correction/conflict detection. All injected HTTP responses, including source-excerpt replays, carry `synthetic_fixture` origin; their counts cannot establish live success and the inherited approval gate rejects them. Simulated 2024 header/value changes are **not** an actual CODATA release or scientific measurement. The current official NIST page identifies the 2022 adjustment; its May 2024 content-update date does not create a 2024 CODATA adjustment.

NIST's selected values are evaluated reference constants with CODATA standard uncertainty, not direct measurements made by this experiment. Monitoring identifies them as `reference_constant` without rewriting their inherited raw classification. PubChem molecular descriptors and Materials Project structural densities are computed properties. No direct experimental-measurement connector is implemented. Missing source uncertainty, publication details, measurement date and T/P validity remain unknown; no ambient-condition validity or source licence is inferred. No model extrapolation, new physical dynamics or general chemistry capability is introduced. Physical conservation/audit rules remain those of unchanged 010/011, verified by regressions and the object-recovery demo.

Independent checks establish record/capture agreement, dimensional consistency within the existing registry and reproducibility. They do not establish that a source value is scientifically correct, uniquely applicable to a laboratory material, or licensed for every use. Human scientific and licensing review remains necessary; no acquisition path approves or publishes anything.

## Change detection

Each retrieval has a durable run and per-record observation, even if exact source bytes or scientific content repeat. Scientific values are normalized for comparison while original units/conditions/uncertainties remain stored. Comparison is against the latest accepted matching key, fixing Experiment 012's tendency to classify a return to any historical value as a duplicate.

- `new`: not previously covered locally or in the baseline.
- `unchanged`: equal latest scientific content; metadata changes remain flagged.
- `correction`: differing content with a demonstrably newer ordered CODATA adjustment year; still a review candidate.
- `conflict`: differing latest content without an established newer ordered release, including same-version differences, older releases, reversions and changed PubChem snapshot hashes.
- `missing` / `rejected`: unknown value or unsupported/invalid evidence/format.

A later retrieval timestamp, a new content hash or a resource Last-Modified header alone does not prove scientific correction. The system never selects a winning conflict or automatically replaces the authoritative catalogue. MP versions currently lack an implemented ordering policy, so differing MP values remain conflicts. Publication references unsupported by the selected endpoint are explicitly unavailable; the pipeline does not invent citations.

## Persistence and operational controls

Experiment 013 opens only a fresh or explicitly marked 013 staging database. It refuses old 012 staging and other existing databases without writing them. The inherited schema is supplemented by immutable runs, results, exchanges and observations, a cache-origin table and fenced verification jobs. Exact response bodies and metadata digests survive parser failures; source records remain append-only. SQLite full synchronization and atomic observation/result commits support restart recovery.

Transport uses normal verified TLS and the configured proxy, forbids redirects, limits source endpoints and response size, reserves one request/second per source, and bounds socket timeouts/retry attempts. Numeric and HTTP-date Retry-After values and provider throttling signals produce durable cooldown. Policy/authentication/permission errors terminate rather than trigger attempts to bypass restrictions. Reports omit exception text that might contain credentials; request headers and cookies are not persisted. Bounded upstream error bodies are retained locally where available, so local database access must be restricted, particularly with credentialed sources. No generated database or credential is uploaded in the PR.

Five-minute durable job leases use ownership tokens to reject stale worker completion. Expired acquisition runs become interrupted; their evidence stays available and new retrievals get new run identities. A tick is explicitly invoked and bounded, not a background daemon. No service, cron entry or continuous source request loop is installed.

## Validation results

`test_results.json` contains full logs and historical hash checks:

| Suite | Tests | Result |
|---|---:|---|
| Experiment 010 | 11 | Pass |
| Experiment 011 | 25 | Pass |
| Experiment 012 | 41 | Pass |
| Experiment 013 | 43 | Pass |
| Total | 120 | Pass |

The new suite covers repeated observations, latest-record comparisons, ordered correction candidates, older-version conflicts, reversions, metadata-only changes, computed-property classification, missing density, source timestamps/exact bytes, independent parsing, identity mismatch, hash/metadata corruption, append-only evidence, cache origin, forced refresh, interrupted runs, scheduled failures/recovery, fenced leases, deterministic timeout/retry/rate-limit scenarios, persistent cooldown, 403/permission/policy denials, response limits, opt-in safeguards and pinned object recovery.

`offline_results.json` records 11 passing checks: new/unchanged/synthetic-correction/synthetic-conflict detection, reversion classification, explicit scheduled tick, equal staging monitoring after restart, unchanged previous catalogue/world/lab bytes, recovered dataset pin, no approval/publication, and no claimed live successes.

`live_results.json` records two permitted finite rounds per requested source. NIST and PubChem each have zero successful responses and two destination-policy failures; Materials Project has two access checks reporting a missing API key and zero external requests. Response dates, source Last-Modified and scientific values are unknown because no upstream response was received. The live success flag is false, not skipped or counted as a pass. Initial restricted-execution probes also failed; the delivered run was performed after session network permission was granted and specifically reached the proxy's destination denial. No source authentication or licensing restriction was bypassed.

## Primary documentation reviewed

- [NIST constants](https://physics.nist.gov/cuu/Constants/) and [official bulk text endpoint](https://physics.nist.gov/cuu/Constants/Table/allascii.txt). The current reference is CODATA 2022, not the synthetic fixture's changed year.
- [NIST licensing/SRD guidance](https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications). SRD rights require specific review; no broad grant is assumed.
- [PubChem PUG REST documentation](https://pubchem.ncbi.nlm.nih.gov/pcfe/docs/markdown/pug-rest.md) and [download/licensing guidance](https://pubchem.ncbi.nlm.nih.gov/docs/downloads). The documented maximum is five requests/second; this implementation uses one/second and respects provider cooldown. Contributor rights remain unresolved in staging.
- [Materials Project API documentation](https://docs.materialsproject.org/downloading-data/using-the-api/getting-started), [terms](https://materialsproject.org/about/terms) and [official open-data registry](https://registry.opendata.aws/materials-project/). API use requires a key and applicable terms; this work declares neither credential readiness nor completed terms review.

Browser access to documentation is not an automated scientific API success or an exact response fixture. The earlier NIST excerpt's transcription provenance remains unchanged. No successful new live scientific fixture could be recorded in this environment.

## Outstanding work and limitations

Enable permitted NIST/PubChem hosts through the managed environment configuration workflow, then rerun the opt-in demonstration to produce successful exact real responses and test unchanged observations over time. Obtain MP credentials through the owner's normal account process, review current terms, and run credentialed checks only with permission. These are outstanding prerequisites, not completed deliverables. The [cloud runtime networking instruction](skill://plugin_connector_1p_c5b7d5df5d7081918f2c4be5a633ed5d/cloud-environment-runtime/references/networking.md) requires the supported workflow for an explicit destination denial and forbids proxy bypass.

No production integration claim follows from simulated tests. Source schema, current licences and authentic correction histories still need permitted live validation. Only explicit curated identities are supported; no autonomous discovery, accounts, shared university systems or agents are implemented. Existing illustrative models remain illustrative. The dimensional registry is intentionally narrow; no general arbitrary-unit algebra or calibrated T/P model is added.

Evidence hashes detect accidental tampering, not an adversary who can replace hashes or alter the filesystem. Review identity remains a declared trusted-operator action rather than authenticated/signed approval. Separate staging databases/deployments do not share rate coordination. A socket timeout and pre-request time budget do not provide a hard wall-clock bound for every possible OS stall or slowly streaming response. A stalled worker can outlive its lease; completion fencing protects job state but external duplicate requests cannot be universally prevented. Failed partial release recovery remains Experiment 012's documented limitation; 013 does not publish releases.

Recommended next work: complete permitted live validation before expanding coverage; capture two genuine official source releases to establish a real correction history; add reviewed compound/crystal/material mappings and source-specific licensing decisions. Only then consider controlled unattended acquisition and stronger signed review/release recovery.
