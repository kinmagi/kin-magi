# Curious Worlds — Experiment 011: scientific reference integration

Date: 2026-10-08 UTC. Baseline: `kinmagi/kin-magi` main commit `a2159eb6bc1732bd5d6cfc0d63a2c3e976f0f4ff`, containing the completed Experiment 010. All new files live in `experiment011/`. Experiment 010's eight Git blobs are preserved exactly and checked by a test. No earlier experiment, database or history is migrated or overwritten. No autonomous agents, account system or university interface is introduced.

## Outcome and scientific scope

Implemented a reproducible SQLite reference catalog, an explicit SI unit layer and a persistent laboratory-object adapter. The initial release is `cw011-2026-10-08.1`; its canonical JSON SHA-256 is `5595729dd86d2f8e80a4c4c6c23021f8fe1f1d1f8b29302cc5fde230dfb5f906`. It contains 18 source/provenance entries, four elements, nine isotopes, four material identities, 24 physical-property records and five constants. Seven physical properties are populated; 17 are explicitly unknown. This is a verified transcription/traceability exercise, not an independent measurement campaign or a general physics/chemistry engine.

| Coverage | Included | Scientific classification and limits |
|---|---|---|
| Elements | H, O, Al, Cu; atomic numbers and standard atomic weights | Source compilations. H/O weights remain intervals; no invented midpoint. |
| Isotopes | H-1/2/3, O-16/17/18, Al-27, Cu-63/65 | Relative atomic masses and representative mole fractions; H-3 abundance unknown. |
| Metals | Copper, aluminum | Nominal elemental compositions and STAR density constants. |
| Other material | Liquid water | Nominal STAR mass fractions and density; no EOS or calibrated temperature dependence. |
| Alloy | 6061-T6 aluminum, UNS A96061 | Grade/temper identity and published thermal fits; certified batch composition unknown. |
| Density | Three nominal values | Temperature and pressure unspecified by selected source; condition-specific queries rejected. |
| Melting temperature | Copper nominal fusion temperature | Source-supplied TRC uncertainty retained; pressure unspecified. |
| Thermal conductivity | 6061-T6 temperature correlation | Source approximation, evaluated only within 4–300 K. |
| Specific heat | 6061-T6 temperature correlation | Source approximation, evaluated only within 4–300 K. |
| Molar heat capacity | Copper solid Shomate equation | Source approximation, source range 298–1358 K; local conservative solid cap 1357 K. |
| Electrical resistivity | Schema and units supported | Unknown for all four materials; no inferred values. |
| Constants | c, k_B, N_A, G, m_u | Exact SI definitions distinguished from CODATA adjusted measured values. |
| Pressure dependence | Metadata and query validation | No numeric coverage curated; all explicit pressure requests rejected for this release. |

The requested categories are represented by a modular storage/retrieval system, not by complete coverage. Source-verified facts may themselves be nominal assumptions or fitted values. Those distinctions are retained. Copper/aluminum elemental media are not interchangeable with certified batches or grades such as OFHC. Alloy composition is not fabricated from its name, and no mixture property is calculated from composition.

## Sources, curation and rights

Primary pages were inspected via the browser on the access date. Values in `dataset.json` and `make_dataset.py` are direct transcriptions of observed source numerals. Units, source references, stated ranges and available uncertainties were checked at the same time. No scientific number was generated from an AI prediction or an unsourced recollection. `make_dataset.py` reconstructs the curated JSON; it is not a network importer. The fingerprint identifies the entire local curation, including source/condition/uncertainty metadata. It does not purport to hash the source websites.

- [NIST atomic compilation](https://www.nist.gov/pml/atomic-weights-and-isotopic-compositions-relative-atomic-masses): last data update January 2015; atomic weights 2013, isotopic compositions 2009 and AME2012 relative masses. These are pinned historical source versions, not a claim to the latest isotope evaluation. NIST describes this compilation as convenience data rather than a fresh critical evaluation.
- NIST STAR nominal compositions and densities: [copper](https://physics.nist.gov/cgi-bin/Star/compos.pl?matno=029), [aluminum](https://physics.nist.gov/cgi-bin/Star/compos.pl?matno=013), [water](https://physics.nist.gov/cgi-bin/Star/compos.pl?matno=276). Preserve the source's precision and missing conditions. The radiation-evaluation context does not justify assigning room-temperature measurement conditions.
- [Copper thermochemistry](https://webbook.nist.gov/cgi/cbook.cgi?ID=C7440508&Mask=2), NIST WebBook SRD 69, Chase (1998), data reviewed June 1977: use only the published solid Cp equation. [Copper fusion data](https://webbook.nist.gov/cgi/cbook.cgi?ID=C7440508&Mask=4): preserve the nominal catalog characterization and assigned uncertainty.
- [6061-T6 cryogenic correlations](https://trc.nist.gov/cryogenics/materials/6061%20Aluminum/6061_T6Aluminum_rev.htm): logarithmic fits with separate data/equation ranges and fit-error descriptions. Conductivity's equation extends to 1 K, but the source data begin at 4 K; this implementation uses the supported overlap. Bibliographic attribution follows the [NIST reference page](https://trc.nist.gov/cryogenics/materials/references.htm).
- [2022 CODATA constants](https://physics.nist.gov/cuu/Constants/Table/allascii.txt), [SI dimensions/Celsius definitions](https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-4-two-classes-si-units-and-si-prefixes), [conversion factors](https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b8), and the NIST explanation of [mass-energy equivalence](https://www.nist.gov/si-redefinition/kilogram/kilogram-mass-and-plancks-constant).

A direct NIST fluid-data request for a small water pressure series could not be retrieved through the available browser tool. No pressure-dependent values were imported from that failed request. This access result is not a claim that reliable pressure data do not exist; it is a reason to leave that coverage unknown here. PubChem was not needed for the initial curation and no PubChem data were imported.

[DATA_NOTICES.md](DATA_NOTICES.md) retains attribution, access/version context, SRD 69 copyright identification and links to NIST's source terms. SRD compilations are not assumed to be public-domain simply because access is free. Only small attributed factual excerpts are included; source pages, complete databases and subscription products are not redistributed. Larger imports need product-specific rights review and explicit curation. No NIST endorsement or blanket downstream licence is claimed.

## Architecture and database schema

`schema.sql` creates separate tables for `dataset`, `source`, `element`, `isotope`, `material`, `property` and `constant`. Scientific entities and properties are keyed by dataset version; foreign keys require valid scientific source and material references. Property records store status, units, conditions and uncertainty explicitly, with the complete canonical record retained as JSON. The dataset table stores a canonical manifest and SHA-256 fingerprint. Source provenance includes upstream release (or a clear absence of release identifier), access date, URL, title, bibliography, rights context and verification method.

`build()` validates identity, composition, numerical finiteness, dimensions, uncertainty metadata, explicit coverage and registered model schemas before exclusively creating a new SQLite file. It never overwrites an existing file. It imports one release manifest per file. Composite schema keys allow later multi-release catalog tooling, but automatic import aggregation/migration is not implemented. Preserve old catalog files for objects pinned to those releases.

`Catalog` opens SQLite read-only and enables query-only behavior. It checks integrity, foreign keys, manifest hash and the correspondence of every normalized row to the release manifest. Reads recheck these invariants to detect accidental external edits before resolving data. An explicit `ReferenceProvider` protocol separates the adapter from a concrete catalog implementation. Requests require an exact dataset version; there is no implicit `latest` or approximate material-name matching.

Known records have their scientific source. Unknown records have a null source and a precise missing-coverage explanation, since inventing a citation would also be scientifically dishonest. Each material has entries for all six implemented physical-property names, even when the value is unknown. `record()` returns that metadata; `property()` raises `UnsupportedProperty` rather than returning a guessed number. Missing identities, missing versions, unsupported units, incompatible dimensions, wrong phases, unsupported pressure conditions and temperatures outside model limits fail closed.

The unit registry uses six SI exponents (mass, length, time, temperature, amount, current). Decimal arithmetic handles exact prefix conversions and the Celsius offset. Absolute temperatures and temperature differences have separate semantics; uncertainty conversion applies scale, never an absolute offset. Molar and mass-specific heat capacities cannot be converted without a separately specified physical model. Logarithmic fits use dimensionless T/(1 K) and y/(source output unit); Shomate uses dimensionless T/(1000 K). Published coefficients are applied in their prescribed output units.

The pure rest-energy query demonstrates a calculated value from an established model, E=m*c², with a dimension-checked result in joules and separate provenance for the equation and c. It is a lookup/calculation interface, not an operation that changes mass or adds usable energy to a world object. Input mass uncertainty is not supplied; output uncertainty remains explicitly unreported.

## Engine integration and conservation

`Laboratory(path, world, catalog)` takes an existing Experiment 010 world and stores laboratory objects in a separate database. Each object records its engine region, material identity, dataset version, scientific content hash, mass and object version. Its reference is resolved at query time against the pinned catalog. A replacement catalog with the same release label but different content is rejected. Missing old releases are rejected rather than silently substituting newer ones.

The laboratory sidecar stores its own hash-chained before/after event history and materialized objects. It is bound to the engine world's first immutable event hash, preventing accidental attachment to a different world with the same region indices. Startup replays the laboratory history, rechecks scientific references and compares replay with current objects. Events cannot be updated/deleted through ordinary SQL without triggering rejection. Actor text is provenance, not authenticated identity.

Object creation explicitly introduces an inventory, recorded as such. It is not a solver for creating matter. The only mutable object operation is a validated mass transfer between two objects with identical material/release/hash identity. Under BEGIN IMMEDIATE it checks current versions, source sufficiency, target identity, nonnegativity and conservation, then atomically updates both objects and an event. Rejected proposals do not change objects/events. The Decimal ledger permits 0–10^12 kg per object in increments of 10^-9 kg, avoiding unnoticed small transfers lost to arithmetic rounding. Higher ranges or finer precision are unsupported.

The adapter does not write Experiment 010 region/event tables or the catalog, and reference queries do not change the world. Tests also demonstrate the reverse: a normal engine erosion commit leaves laboratory objects and the catalog unchanged. There is no cross-database physical operation; consequently no distributed transaction is needed or claimed. Future coupled region/object dynamics require an explicit atomicity design.

SQLite FULL synchronization and transactions recover uncommitted laboratory writes after process exits and preserve committed writes. Tests include a new process, rollback after an event-insert failure, and abrupt exits both before and after commit. Device/filesystem synchronization behavior still determines physical power-loss guarantees. Hashes detect accidental inconsistencies but are not publisher signatures or protection against an administrator rewriting an entire database and its hashes.

## Validation and recorded results

`python run_tests.py --out <fresh_path>` runs both suites in separate import contexts. **36 tests pass: all 11 unchanged Experiment 010 tests and 25 Experiment 011 tests.** Recorded run: Python 3.12.14, baseline suite 0.167 s and new suite 1.631 s. Exact environment version is retained in `test_results.json`.

| Required testing area | Evidence |
|---|---|
| Source traceability | Every populated property resolves source/units/conditions/uncertainty; known atomic/source facts checked. |
| Units and dimensions | Prefixes, density, bar/Pa, Celsius/kelvin, temperature differences, uncertainty scaling; incompatible dimensions and unknown units rejected. |
| Material identity/composition | Element atomic numbers, isotope identity, mass fractions, alloy grade/temper and unknown batch composition; malformed composition rejected. |
| Missing properties | All resistivity records unknown; arbitrary properties and material aliases rejected. |
| Scientific classifications | Nominal densities/fusion, source approximations, exact constants, adjusted measured constants and model calculations remain distinct. |
| Numerical model validation | Copper Cp agrees with five independently published rounded NIST table values; alloy fits agree with independent high-precision Decimal evaluation at three temperatures. |
| Dataset versioning | Content hash, exact version lookup, exclusive builder, separate release files, missing-version and content-mismatch rejection. |
| Persistent object references/restart | Catalog/world/lab reopening, event replay and pinned references; subprocess recovery before/after commit. |
| Isolation/conservation | Reference-file SHA-256 unchanged by lab/engine operations; world history/state preserved; conserved same-material mass transfer. |
| Rejection/concurrency/audit | Stale two-client proposals, excessive mass, mixed identities, malformed inputs, insertion-fault rollback and tamper checks. |
| Compatibility | All 11 baseline tests; eight upstream Git blob hashes checked exactly. |

The integration demo passes all seven checks: unknown-property rejection, excessive-transfer rejection, recovered objects, engine state isolation, preserved engine events, verified read-only reference catalog and mass conservation. It starts with one engine region and a validated illustrative erosion event, introduces a 1 kg 6061-T6 object plus an empty receiver, then transfers 0.1 kg, recovering masses 0.9 kg and 0.1 kg after restart. The laboratory audit contains three events; the engine retains its two generation/erosion events.

Calculated source-fit demonstrations at 100 K: 6061-T6 specific heat approximately 492.1982 J/(kg K), thermal conductivity approximately 97.70122 W/(m K). These are evaluated approximations, not fresh measured results. The source's respective curve-fit errors (5% and 0.5% relative to its data) are retained as fit descriptors, not converted into standard measurement uncertainties. Additional digits in the recorded JSON are computational output, not justified experimental precision.

## Limitations and next experiment

The initial set is small and historical where explicitly versioned. Source checking is manual browser inspection, not a continuous source monitor. Automated tests validate curation consistency and code contracts; they cannot establish the truth of a newly supplied scientific number solely from a URL. A future import needs primary-source review and a new release fingerprint. No live source calls occur at runtime or during tests.

Representative isotope abundances need not describe a particular specimen, and their uncertainty semantics are not necessarily Gaussian. Standard atomic-weight intervals must not be treated as scalar point measurements. Relative atomic masses and weights are dimensionless ratios; this release does not silently interpret them as kilograms or exact g/mol values. Fit uncertainties/covariances are incomplete, so a full propagated uncertainty budget is not implemented. Lack of uncertainty is stored as null, never zero by default.

No pressure-dependent numerical dataset, EOS, electrical resistivity values, alloy batch composition, automatic composition-derived properties, reactions, heating solver, phase-transition dynamics, energy/momentum state model, mechanical simulation or autonomous agents are implemented. Reference objects do not turn Experiment 010's illustrative coastal accounting into calibrated physics. Catalog checks/replays are deliberately exhaustive for a small release and will need indexing/verification strategy work before large-scale ingestion. Package installation, migrations, cross-file coupled transactions and production load/performance studies are outside this experiment.

Recommended Experiment 012: add a narrowly curated, condition-specific measured dataset or a few authoritative water EOS state points, with source version, temperature/pressure/phase, documented uncertainty and reuse rights. Distinguish source-model outputs from experimental measurements; permit exact tabulated state-point lookups before introducing interpolation. Independently verify the values and interpolation error budget, preserve old releases, and add audit/persistence tests for whatever new physical operations are actually implemented. Continue to defer autonomous agents and interfaces until scientific coverage and uncertainty handling support them.
