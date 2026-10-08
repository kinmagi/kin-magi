import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from engine import World
from models import inventories

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'world.sqlite';self.w=World(self.path)
    def tearDown(self):self.w.close();self.tmp.cleanup()
    def execute(self,op,targets,id='p'):
        self.w.submit(id,'human-test',self.w.propose(op,targets));return self.w.commit(id)
    def test_persistence_and_idempotent_revisit(self):
        self.w.explore(1);self.execute('erosion',[1]);before=self.w.state();self.w.close();self.w=World(self.path)
        self.assertEqual(before,self.w.state());self.assertFalse(self.w.explore(1)[1]);self.assertEqual(2,len(self.w.events()))
    def test_rejections_leave_state_events_unchanged(self):
        self.w.explore(0);p=self.w.propose('erosion',[0]);before=self.w.state();events=self.w.events()
        bads=[None,{},dict(p,operation='chemistry'),dict(p,versions={'0':-1})]
        for field,value in [('shore_tonnes',-1),('shore_tonnes',True),('shore_tonnes',111),('right_boundary_mm',10500)]:
            bad=copy.deepcopy(p);bad['after']['0'][field]=value;bads.append(bad)
        for i,bad in enumerate(bads):
            self.w.submit(str(i),'ai-fixture',bad);self.assertFalse(self.w.commit(str(i))['accepted'])
            self.assertEqual(before,self.w.state());self.assertEqual(events,self.w.events())
        with self.assertRaises(ValueError):self.w.submit('nan','ai-fixture',{'x':float('nan')})
    def test_conservation_and_equal_levels(self):
        self.w.explore(0);before=inventories(self.w.state());self.assertTrue(self.execute('equalization',[0])['accepted'])
        s=self.w.state()['0'];self.assertAlmostEqual(s['volumes_m3']['A']/10000,s['volumes_m3']['B']/20000)
        for i in range(60):self.execute('erosion',[0],str(i))
        self.assertEqual(before,inventories(self.w.state()));self.assertEqual(0,self.w.state()['0']['shore_tonnes'])
    def test_boundaries_order_and_limits(self):
        for i in [10,-3,9,-2,0,1]:self.w.explore(i)
        s=self.w.state()
        for a,b in [(9,10),(-3,-2),(0,1)]:self.assertEqual(s[str(a)]['right_boundary_mm'],s[str(b)]['left_boundary_mm'])
        for bad in [True,1.0,'A',1000001]:
            with self.assertRaises(ValueError):self.w.explore(bad)
    def test_cross_region_atomic_conservation(self):
        self.w.explore(0);self.w.explore(1);self.execute('erosion',[0],'e');before=inventories(self.w.state())
        self.assertTrue(self.execute('boundary_transfer',[0,1],'t')['accepted']);self.assertEqual(before,inventories(self.w.state()))
        self.assertEqual(1,self.w.state()['1']['offshore_tonnes']);self.assertTrue(self.w.verify()['verified'])
    def test_two_connections_stale_and_retry(self):
        self.w.explore(0);p=self.w.propose('erosion',[0]);other=World(self.path)
        try:
            other.submit('second','future-client',p);self.execute('erosion',[0],'first')
            self.assertFalse(other.commit('second')['accepted']);self.assertTrue(self.w.commit('first')['accepted'])
            self.assertEqual(2,len(self.w.events()))
        finally:other.close()
    def test_fault_rolls_back_state_event_and_status(self):
        self.w.explore(0);before=self.w.state();self.w.submit('p','test',self.w.propose('erosion',[0]))
        self.w.db.execute("CREATE TRIGGER fail_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'fault'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.w.commit('p')
        self.assertEqual(before,self.w.state());self.assertEqual('pending',self.w.db.execute('select status from proposals').fetchone()[0])
        self.w.db.execute('DROP TRIGGER fail_event');self.assertTrue(self.w.commit('p')['accepted'])
    def test_process_restart_and_uncommitted_crash(self):
        self.w.explore(0);self.execute('erosion',[0]);before=self.w.state()
        code="from engine import World; import json,sys; w=World(sys.argv[1]); print(json.dumps(w.state())); w.close()"
        got=subprocess.check_output([sys.executable,'-c',code,str(self.path)],text=True)
        self.assertEqual(before,json.loads(got))
        crash="from engine import World; import os,sys; w=World(sys.argv[1]); w.db.execute('BEGIN IMMEDIATE'); w.db.execute(\"DELETE FROM regions\"); os._exit(9)"
        self.assertEqual(9,subprocess.run([sys.executable,'-c',crash,str(self.path)]).returncode)
        self.w.close();self.w=World(self.path);self.assertEqual(before,self.w.state());self.assertTrue(self.w.verify()['verified'])
    def test_crash_after_commit_and_pending_recovery(self):
        self.w.explore(0);self.w.submit('p','test',self.w.propose('erosion',[0]));self.w.close();self.w=World(self.path)
        code="from engine import World; import os,sys; w=World(sys.argv[1]); w.commit('p'); os._exit(7)"
        self.assertEqual(7,subprocess.run([sys.executable,'-c',code,str(self.path)]).returncode)
        self.w.close();self.w=World(self.path);self.assertTrue(self.w.commit('p')['accepted']);self.assertEqual(2,len(self.w.events()))
    def test_audit_tamper_detected(self):
        self.w.explore(0)
        with self.assertRaises(sqlite3.IntegrityError):self.w.db.execute('DELETE FROM events')
        self.w.db.execute("UPDATE regions SET data='{}'");self.assertRaises(ValueError,self.w.verify)
    def test_refuse_legacy_and_model_mismatch(self):
        legacy=Path(self.tmp.name)/'legacy.sqlite';c=sqlite3.connect(legacy);c.execute('create table world(x)');c.close()
        with self.assertRaises(ValueError):World(legacy)
        self.w.db.execute("UPDATE metadata SET value='999'")
        with self.assertRaises(ValueError):World(self.path)

if __name__=='__main__':unittest.main(verbosity=2)
