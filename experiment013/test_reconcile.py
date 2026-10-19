"""Isolated recovery regression tests. No delivered datasets or releases are touched."""
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "experiment012"))
from pipeline import Stage
from compat import ROOT
from connectors import NIST
from reconcile import inspect, repair, RecoveryError


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.stage = Stage(self.root / "stage.sqlite")
        body = ROOT.joinpath("fixtures/nist_excerpt.txt").read_bytes()
        evidence = json.loads(ROOT.joinpath("fixtures/nist_excerpt_metadata.json").read_text())
        self.stage.capture(body, evidence)
        record = NIST().parse(body, evidence)[0]
        selected = self.stage.ingest([record])[0]
        self.candidate = self.stage.candidate([selected], "cw012-reconcile-test.1")
        self.version = self.candidate["version"]
        self.releases = self.root / "releases"
        self.stage.approve(self.candidate["hash"], "Unit test reviewer", "Temporary test authorization only", licenses_reviewed=True)
        self.stage.publish(self.candidate["hash"], self.releases)
        self.target = self.releases / self.version

    def tearDown(self):
        self.stage.close()
        self.temp.cleanup()

    def delete_publication_record_for_fixture(self):
        # The production audit is append-only; only test fixtures may drop that trigger.
        self.stage.db.execute("DROP TRIGGER no_publications_delete")
        self.stage.db.execute("DELETE FROM publications WHERE version=?", (self.version,))

    def test_intact_package_is_consistent_and_not_repairable(self):
        self.assertEqual(inspect(self.stage, self.releases, self.version)["status"], "consistent_published")
        with self.assertRaises(RecoveryError):
            repair(self.stage, self.releases, self.version, operator="tester", authorization="TEST-1")

    def test_interrupted_without_ready_is_quarantined(self):
        (self.target / "READY").chmod(0o644)
        (self.target / "READY").unlink()
        self.assertEqual(inspect(self.stage, self.releases, self.version)["status"], "quarantined_incomplete")
        with self.assertRaises(RecoveryError):
            repair(self.stage, self.releases, self.version, operator="tester", authorization="TEST-1")

    def test_complete_missing_record_requires_operator(self):
        old = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.target.iterdir()}
        self.delete_publication_record_for_fixture()
        self.assertEqual(inspect(self.stage, self.releases, self.version)["status"], "verified_missing_record")
        with self.assertRaises(RecoveryError):
            repair(self.stage, self.releases, self.version, operator="", authorization="TEST-1")
        self.assertEqual(repair(self.stage, self.releases, self.version, operator="tester", authorization="TEST-1")["status"], "repaired")
        self.assertEqual(inspect(self.stage, self.releases, self.version)["status"], "consistent_published")
        self.assertEqual(old, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.target.iterdir()})

    def test_tampered_ready_refused(self):
        self.delete_publication_record_for_fixture()
        p = self.target / "READY"
        p.chmod(0o644)
        p.write_text("0" * 64 + "\n")
        with self.assertRaises(RecoveryError):
            inspect(self.stage, self.releases, self.version)

    def test_tampered_catalog_refused(self):
        self.delete_publication_record_for_fixture()
        p = self.target / "catalog.sqlite"
        p.chmod(0o644)
        p.write_bytes(b"not a catalog")
        with self.assertRaises((RecoveryError, sqlite3.DatabaseError)):
            inspect(self.stage, self.releases, self.version)

    def test_unexpected_file_refused(self):
        self.delete_publication_record_for_fixture()
        (self.target / "untracked").write_text("unsafe")
        with self.assertRaises(RecoveryError):
            inspect(self.stage, self.releases, self.version)

    def test_wrong_approval_refused(self):
        self.delete_publication_record_for_fixture()
        self.stage.db.execute("DROP TRIGGER no_approvals_update")
        self.stage.db.execute("UPDATE approvals SET evidence='altered' WHERE candidate_hash=?", (self.candidate["hash"],))
        with self.assertRaises(RecoveryError):
            inspect(self.stage, self.releases, self.version)

    def test_conflicting_record_refused(self):
        self.stage.db.execute("DROP TRIGGER no_publications_update")
        self.stage.db.execute("UPDATE publications SET candidate_hash='wrong' WHERE version=?", (self.version,))
        with self.assertRaises(RecoveryError):
            inspect(self.stage, self.releases, self.version)


if __name__ == "__main__":
    unittest.main()
