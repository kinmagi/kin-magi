# Persistent World — Experiment 010

Date: 2026-10-08 UTC. Implemented separately from uploaded Experiments 005–009. No autonomous agents, API calls or AI credentials were used. The original local path was unavailable; the 27 uploaded files were the source evidence. Attached README instructions were treated as historical documentation, not as new authorization.

## Inspection before implementation

All 27 supplied code, result, documentation and log files were inspected. All nine supplied SQLite databases were opened read-only with immutable access; integrity checks returned `ok`. `source_inventory.json` records byte counts, SHA-256 hashes, database schemas and all stored rows.

| Experiment | Supplied evidence | Implication for 010 |
|---|---|---|
| 005 | Ideal reservoirs conserve approximately 110000 m³; incorrect and stale changes rejected; equilibrium persists. Live and retry results rejected incorrect predictions without events. | Keep the solver authoritative and proposals untrusted. |
| 006 | Solver requested; rounded output rejected at 1e-6 tolerance. Exact-result artifact accepted. Exact variant source was not supplied. | Keep canonical solver output out of prose/rounding pathways. |
| 007 | Exact solver result committed, one event, recovered state received by AI. | Provide a deterministic proposal helper; commit independently recomputes. |
| 008 | Illustrative losses [2,3,1] transfer 6 tonnes from shore to offshore; total 300 tonnes; one event survives restart. | Explicit inventories and conservation validation. |
| 009 | B generated and eroded from 98 to 96 tonnes; C generated; shared boundary 10.4 m; B recovered without regeneration. | Canonical shared boundaries and persistent lazy generation. |

These are supplied historical observations, not newly rerun live AI experiments. The older validator in 005 does not robustly reject NaN (`abs(NaN)>tol` is false), and 008's validator can raise on malformed proposals. Experiment 009 generation compares substrate to another invocation of the same function and uses only three named sections; its event records lack physical payloads. The new engine adds finite-value/schema checks, current-state transaction locking, more region indices, and replayable events. Original experiments were neither imported nor executed against their databases.

## Implementation

Python 3.10+ standard library; SQLite is the sole authoritative store. `models.py` defines a model protocol and three registered deterministic models. `validation.py` rejects malformed, stale, nonfinite, negative, discontinuous and nonconserving proposals. `engine.py` coordinates generation, proposal storage, validation, atomic commit and audit verification. `demo.py` provides a reproducible offline scenario; `test_engine.py` exercises the contracts.

Each region holds two reservoir volumes, shore/offshore sediment and immutable boundaries. Reservoir inventories are independent between regions; sediment can cross a shared boundary in the explicitly implemented transfer operation. This co-locates earlier capabilities without claiming coupled hydrology/coastal dynamics. 010 is a fresh world, not a migration of the earlier changed states. Its initial inventories and uniform substrate are explicitly new model choices.

Regions are generated only when requested, for integer indices from -1000000 to 1000000. A single canonical formula defines each boundary in integer millimetres, so adjacent regions share exactly the same value regardless of generation order. Existing regions are returned from SQLite. Generation reveals an initial inventory: the total of the materialized domain increases as the observed domain expands. This is an accounted generation event, not physical creation during an evolution step; conservation is tested over fixed participating regions. No claim is made to computing an infinite-world inventory.

`World.propose(operation, targets)` is a deterministic producer helper. Any future producer may instead supply an envelope containing operation, expected region versions and candidate after-states. `submit(id, actor, payload)` stores this in `proposals`, separate from authoritative regions. No autonomous producer runs. `commit(id)` locks using BEGIN IMMEDIATE, reads current authoritative state, verifies versions, recomputes the registered model, checks inventories and boundaries, and writes canonical solver values rather than the candidate values. Candidate numerical tolerance is 1e-6 in the field's units; topology/version fields require exact integers. Finite JSON is required at submission. Invalid JSON objects are recorded as rejected; non-JSON values such as NaN fail submission without changing any data.

Accepted changes atomically update all affected regions, their event and proposal status. Rejected changes alter only proposal status/verdict. A repeated commit request returns the stored outcome without another event. Duplicate submission IDs are refused. Two clients proposing changes to the same version cannot both succeed. One SQLite writer at a time is the current concurrency policy; it is suitable groundwork for future producers, not a demonstrated multi-agent runtime.

Committed events include actor, UTC timestamp, operation/model version, proposal ID, full before/after states and chained SHA-256 hashes. Event update/delete triggers block ordinary mutation. Startup checks SQLite integrity, verifies the hash chain, revalidates/replays physical events, and compares replay with materialized state. The event chain detects accidental inconsistency; it is not a signature or protection against a database administrator who rewrites history and its hashes. Proposal rows are not cryptographically chained.

SQLite uses rollback journaling and synchronous=FULL. Startup refuses legacy databases and mismatched model versions; migration is not implemented. Pending proposals survive restart and can be explicitly committed later. Uncommitted SQLite work rolls back following a process crash. Committed work persists. Hardware power-loss durability still depends on the filesystem/device honoring SQLite synchronization guarantees.

## Results

`python -m unittest -v`: **11 tests passed**, 0 failures (recorded run: 0.195 s). Tests cover persistence/revisit, malformed and physical rejection without region/event mutation, nonfinite submission, conservation and depletion, generation order/bounds, two-region transfer, stale proposals from two connections, repeated commit, injected event-insert failure with transaction rollback, separate-process restart, abrupt exit during an uncommitted write, abrupt exit after commit, pending recovery, audit tampering, legacy refusal and model version mismatch.

`python demo.py`: all five scenario checks passed. Two regions generated, reservoir equalization committed, erosion committed, cross-boundary sediment transferred, incorrect AI-fixture proposal rejected, and changed region recovered without regeneration. Five events replay successfully. Total water for the two-region materialized domain is 220000 m³ and sediment is 200 tonnes. Region 1 reservoir volumes are approximately 36666.6666667 and 73333.3333333 m³; equal water levels are 103.6666666667 m. Region 1 shore/offshore sediment is 98/1 tonnes and region 2 is 100/1 tonnes. This conserved transfer is illustrative, not a validated transport process.

The completed local run produced `world010.sqlite`, `results010.json`, `tests.log`, and preservation verification. Original uploads remain in the local `sources/` directory; hashes of all 27 original upload files were checked after implementation. This GitHub transfer includes only Experiment 010 source, tests and documentation; generated databases/results/logs and historical source copies are excluded.

## Scientific scope and limitations

Reservoir equalization is an ideal hydrostatic equilibrium calculation for equal 100 m beds, fixed vertical sides, A=10000 m² and B=20000 m², open connection and no inflows/losses. It calculates an endpoint, not elapsed time or fluid dynamics. Water volume conservation represents mass conservation only under the constant-density assumption; density is not modeled.

Erosion (up to 2 tonnes per application) and offshore transfer (up to 1 tonne left-to-right) are accounting illustrations without a time unit, calibration, waves, forces or empirical transport laws. Fixed boundary elevations demonstrate continuity of an immutable one-dimensional substrate; they do not demonstrate changing terrain continuity. Uniform generation is deterministic, not a scientifically characterized landscape generator. There is no chemistry, heat/energy conservation model, momentum model, weather, biological simulation, 2D/3D mesh, sediment-water feedback, autonomous agent, live AI test, authentication service, schema migration or production performance study.

The validator is independent of the proposal producer, but uses the same approved model implementation as the convenience solver. Tests independently check conservation/equal levels and known scenario outputs; they do not constitute a second independently implemented numerical solver or scientific calibration. Recovery checks are linear in event history and snapshots/compaction are not yet implemented. Python API users can inspect the SQLite connection, so this is a modular authority contract, not a sandbox against malicious in-process code.

## Recommended Experiment 011

Keep autonomous agents deferred. Define a calibrated, time-dependent two-reservoir flow model with explicit connection conductance, timestep, density assumptions and closed-domain boundaries. Compare against analytic solutions or an independently implemented reference solver, measure timestep convergence and error budgets, and record model provenance/units in every event. Extend boundary tests only when dynamic exchange is physically defined. Then run longer histories and concurrent producer load tests before adding autonomous agents. Calibration data must be identified and justified before describing any coastal model as physically predictive.

## Reproduction

In a copy of this directory, run:

```sh
python -m unittest -v
python demo.py --db fresh_world.sqlite --out fresh_results.json
```

The demo refuses existing database/result paths. Tests use disposable temporary databases. Do not use earlier experiment databases as targets.
