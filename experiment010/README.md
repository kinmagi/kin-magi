# Experiment 010

Standard-library Python world engine with SQLite authority, validated proposals, lazy regions and auditable changes. No agents or network/API calls. Read REPORT.md for scientific scope and limitations.

Run `python -m unittest -v`. Run a new scenario with `python demo.py --db fresh_world.sqlite --out fresh_results.json` (existing paths are refused).

API: World(path), explore(index), state(), propose(operation, targets), submit(id, actor, payload), commit(id), events(), verify(), close(). Operations: equalization, erosion, boundary_transfer. Proposal envelope: operation, versions (region string IDs to current integer versions), after (region string IDs to candidate states). Actor is provenance text, not authenticated identity. Always close a World connection.

From the repository root, first run `cd experiment010`. Generated databases, results, caches and environments are excluded by the directory .gitignore. Historical Experiments 005–009 are not included or modified by this transfer.
