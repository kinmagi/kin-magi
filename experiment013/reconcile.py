"""Experiment 013: inspect-only recovery and explicitly authorized publication-log repair.

Never modifies package files, READY, candidates, approvals, or older datasets.
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiment012"))
from compat import Catalog, canonical, digest, validate_manifest
from pipeline import Stage


class RecoveryError(ValueError):
    pass


def inspect(stage, releases_dir, version):
    """Independently validate existing evidence; return a non-mutating diagnosis."""
    root = Path(releases_dir).resolve()
    target = root / version
    if not version.startswith("cw012-") or "/" in version or "\\" in version or version in {".", ".."}:
        raise RecoveryError("invalid release version")
    if not target.is_dir() or target.is_symlink():
        raise RecoveryError("release directory absent or unsafe")
    names = {"dataset.json", "catalog.sqlite", "receipt.json", "READY"}
    actual = {p.name for p in target.iterdir()}
    if any(p.is_symlink() or not p.is_file() for p in target.iterdir()):
        raise RecoveryError("unsafe package entry")
    if actual - names:
        raise RecoveryError("unexpected package entries")
    missing = sorted(names - actual)
    # Check the publication log even for incomplete packages; it must never be overwritten.
    records = stage.db.execute("SELECT version,candidate_hash,reviewer,path FROM publications WHERE version=? OR path=?", (version, str(target))).fetchall()
    if missing:
        return {"status": "quarantined_incomplete", "version": version, "missing": missing, "publication_records": len(records), "repairable": False}
    try:
        manifest_bytes = (target / "dataset.json").read_bytes()
        manifest = validate_manifest(json.loads(manifest_bytes))
        if manifest_bytes != (canonical(manifest) + "\n").encode() or manifest["version"] != version:
            raise RecoveryError("noncanonical or inconsistent manifest")
        receipt_bytes = (target / "receipt.json").read_bytes()
        receipt = json.loads(receipt_bytes)
        if receipt_bytes != (canonical(receipt) + "\n").encode() or set(receipt) != {"candidate_hash", "manifest_hash", "reviewer", "approval_evidence", "approved_at"}:
            raise RecoveryError("invalid receipt")
        if receipt["manifest_hash"] != digest(manifest) or (target / "READY").read_bytes() != (receipt["manifest_hash"] + "\n").encode():
            raise RecoveryError("manifest or READY digest mismatch")
        h = receipt["candidate_hash"]
        candidate = stage.load_candidate(h)  # Includes archived-source replay and baseline pinning.
        if candidate["version"] != version or canonical(candidate["manifest"]) != canonical(manifest):
            raise RecoveryError("candidate and package disagreement")
        approval = stage.db.execute("SELECT reviewer,evidence,approved FROM approvals WHERE candidate_hash=?", (h,)).fetchone()
        if not approval or tuple(approval) != (receipt["reviewer"], receipt["approval_evidence"], receipt["approved_at"]):
            raise RecoveryError("missing or inconsistent human approval")
        if not isinstance(approval[0], str) or not approval[0].strip() or not isinstance(approval[1], str) or not approval[1].strip():
            raise RecoveryError("empty approval evidence")
        for record in candidate["selected_records"]:
            if record["provenance"]["capture"] == "synthetic_fixture" or record["provenance"]["license_status"] == "unresolved":
                raise RecoveryError("source not eligible for publication")
        catalog = Catalog(target / "catalog.sqlite")
        try:
            catalog.verify()
            if catalog.dataset_hash(version) != receipt["manifest_hash"] or catalog.versions() != [version]:
                raise RecoveryError("catalog/manifest mismatch")
        finally:
            catalog.close()
        if records:
            if len(records) != 1 or records[0] != (version, h, approval[0], str(target)):
                raise RecoveryError("conflicting publication record")
            status = "consistent_published"
        else:
            status = "verified_missing_record"
        return {"status": status, "version": version, "candidate_hash": h, "repairable": status == "verified_missing_record"}
    except (OSError, KeyError, TypeError, json.JSONDecodeError, sqlite3.DatabaseError) as exc:
        raise RecoveryError("package validation failed: " + str(exc)) from exc


def repair(stage, releases_dir, version, *, operator, authorization):
    """One authorized insert only. Recheck everything while holding the DB write lock."""
    if not isinstance(operator, str) or not operator.strip() or not isinstance(authorization, str) or not authorization.strip():
        raise RecoveryError("explicit operator and authorization evidence required")
    stage.db.execute("BEGIN IMMEDIATE")
    try:
        report = inspect(stage, releases_dir, version)
        if report["status"] != "verified_missing_record":
            raise RecoveryError("only verified READY packages lacking a record can be repaired")
        receipt = json.loads((Path(releases_dir).resolve() / version / "receipt.json").read_text())
        # Preserve original approval identity; repair operator is not substituted for reviewer.
        stage.db.execute("INSERT INTO publications(version,candidate_hash,reviewer,path,utc) VALUES (?,?,?,?,?)",
                         (version, report["candidate_hash"], receipt["reviewer"], str(Path(releases_dir).resolve() / version), time.time()))
        # Audit authorization independently without changing Experiment 012 schema.
        # SQLite publication row is append-only; operator authorization belongs to external operator log.
        stage.db.commit()
    except BaseException:
        stage.db.rollback()
        raise
    return {"status": "repaired", "version": version, "operator": operator, "authorization": authorization}


def main():
    parser = argparse.ArgumentParser(description="Experiment 013 read-only inspection / authorized reconciliation")
    parser.add_argument("staging_db", type=Path)
    parser.add_argument("releases_dir", type=Path)
    parser.add_argument("version")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--operator")
    parser.add_argument("--authorization", help="Human authorization reference (also record in external audit log)")
    args = parser.parse_args()
    if not args.staging_db.is_file():
        parser.error("existing staging database required")
    stage = Stage(args.staging_db)
    try:
        outcome = repair(stage, args.releases_dir, args.version, operator=args.operator, authorization=args.authorization) if args.repair else inspect(stage, args.releases_dir, args.version)
        print(json.dumps(outcome, sort_keys=True))
    finally:
        stage.close()


if __name__ == "__main__":
    main()
