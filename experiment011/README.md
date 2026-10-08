# Curious Worlds — Experiment 011

A small, scientifically sourced reference catalog and persistent material-object adapter for the unmodified Experiment 010 engine. Python 3.10+ standard library only. No network calls, keys, agents, university interface or accounts are needed to run it.

Start in this directory:

```sh
cd experiment011
python reference.py --out /tmp/cw011-reference.sqlite
python demo.py --out /tmp/cw011-demo
python run_tests.py --out /tmp/cw011-test-results.json
```

Use fresh output paths. Builders/demos refuse to overwrite existing output. Generated SQLite databases stay out of Git. The checked-in `dataset.json` and `schema.sql` reproduce the scientific reference database. Recorded validation is in `test_results.json` and `demo_results.json`.

Initial coverage: four elements (H, O, Al, Cu), nine isotopes, copper and aluminum metals, liquid water's nominal NIST composition, and 6061-T6 aluminum alloy identity with two cryogenic property fits. Five CODATA constants are included. Source, units, conditions, uncertainty semantics and scientific classification accompany every covered numerical property. Electrical resistivity and other uncovered quantities are explicitly unknown. Alloy batch composition is unknown. Read [REPORT.md](REPORT.md) for scientific limits and [DATA_NOTICES.md](DATA_NOTICES.md) for source attribution/reuse notices.

`Catalog` supports explicit-version lookups of sources, elements, isotopes, materials, composition, constants and property records. A `ReferenceProvider` protocol makes the adapter extensible. There is no implicit `latest` release. `record()` can inspect unknown properties; `property()` raises `UnsupportedProperty` for unknown values, unsupported conditions, phase mismatch and extrapolation. Conditions are `(value, unit)` pairs. Fits are approximations calculated from published coefficients, not new verified measurements.

```python
from reference import Catalog
catalog = Catalog('/tmp/cw011-reference.sqlite')
version = 'cw011-2026-10-08.1'
r = catalog.property('al6061-t6', 'specific_heat', version,
                     temperature=(100, 'K'))
print(r['value'], r['units'], r['status'], r['source']['url'])
catalog.close()
```

`Laboratory(path, world, catalog)` accepts an existing Experiment 010 `World` with at least one explored region. It stores its own objects and audit events in a separate SQLite sidecar and never writes the engine's region/event tables or the catalog. Objects pin `material_id`, `dataset_version` and content hash. The sidecar is bound to the world through its first immutable event hash.

See `demo.py` for engine imports and an end-to-end usage example. Objects are created with `create_object(id, region, material_id, dataset_version, mass)`. Creation explicitly introduces inventory; it is not a physical mass-creation solver. `propose_transfer` / `commit_transfer` validate and atomically conserve mass between objects of the same material and release, rejecting stale versions and unsupported mixing. Mass ledger limits: 0–10^12 kg per object, resolution 10^-9 kg. No reaction, heating, phase change or mechanical dynamics is implemented for these objects.

Nominal densities and copper's nominal melting temperature lack source temperature/pressure conditions; condition-specific requests are rejected. Pressure-dependent numeric coverage is not present in this release. Read-only catalog verification and dataset pinning detect accidental inconsistencies; they do not authenticate a publisher or prevent a database administrator rewriting records and hashes.

Future releases require separate curated manifests and new database files. Preserve older catalogs for older objects. The schema keys data by dataset version, but this release's builder imports one manifest per database and does not automatically merge or migrate catalogs.
