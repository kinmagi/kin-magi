import copy,hashlib,io,json,os,sqlite3,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
from legacy import ROOT,NIST_URL,CONNECTORS,build,AccessUnavailable,canonical,digest
from verification import VerificationStage
from verified_transport import VerifiedTransport
from verified_scheduler import VerificationScheduler
from offline_demo import FixtureResponse

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=[2000000000.]
        self.clock=lambda:self.now[0];self.stage=VerificationStage(self.root/'stage.sqlite',clock=self.clock)
        self.body=ROOT.parent.joinpath('experiment012/fixtures/nist_excerpt.txt').read_bytes()
    def tearDown(self):self.stage.close();self.tmp.cleanup()
    def sleep(self,d):self.now[0]+=d
    def transport(self,body=None,opener=None,**kwargs):return VerifiedTransport(self.stage,opener=opener or (lambda *a,**k:FixtureResponse(body or self.body)),clock=self.clock,sleep=self.sleep,mode='synthetic_fixture',**kwargs)
    def acquire(self,body=None):return self.stage.acquire('nist',transport=self.transport(body))
    def restart(self):
        path=self.stage.path;self.stage.close();self.stage=VerificationStage(path,clock=self.clock)
    def test_new_unchanged_repeated_observations(self):
        self.acquire();self.now[0]+=10;self.acquire();m=self.stage.monitoring();self.assertEqual(m['counts']['new'],1);self.assertEqual(m['counts']['unchanged'],3);self.assertEqual(m['sources']['nist']['completed_runs'],2);self.assertEqual(m['sources']['nist']['http_success_exchanges'],0)
    def test_same_capture_repeat_retains_run(self):
        self.acquire();self.acquire();self.assertEqual(self.stage.db.execute('SELECT count(*) FROM runs').fetchone()[0],2);self.assertEqual(self.stage.db.execute('SELECT count(*) FROM observations').fetchone()[0],4)
    def test_scientific_classification(self):
        self.acquire();m=self.stage.monitoring();self.assertTrue(all(x['scientific_classification']=='reference_constant' for x in m['observations']))
    def test_timestamps_and_exact_bytes(self):
        h={'Date':'Thu, 08 Oct 2026 12:00:00 GMT','Last-Modified':'Wed, 07 Oct 2026 12:00:00 GMT','ETag':'fixture-tag','Set-Cookie':'synthetic-private'}
        self.stage.acquire('nist',transport=self.transport(opener=lambda *a,**k:FixtureResponse(self.body,h)));e=self.stage.monitoring()['exchanges'][0]
        self.assertEqual(e['headers']['last-modified'],h['Last-Modified']);self.assertNotIn('set-cookie',e['headers']);self.assertEqual(self.stage.db.execute('SELECT body FROM exchanges').fetchone()[0],self.body);self.assertEqual(e['sha256'],hashlib.sha256(self.body).hexdigest())
    def test_correction_is_only_candidate(self):
        self.acquire();new=self.body.replace(b'2022 CODATA',b'2024 CODATA').replace(b'9.109 383 7139 e-31',b'9.109 383 7138 e-31');self.acquire(new)
        m=self.stage.monitoring();self.assertEqual(m['counts']['correction'],1);self.assertEqual(m['approved_count'],0);self.assertEqual(m['published_count'],0)
    def test_conflict_same_version(self):
        self.acquire();self.acquire(self.body.replace(b'9.109 383 7139 e-31',b'9.109 383 7138 e-31'));self.assertEqual(self.stage.monitoring()['counts']['conflict'],1)
    def test_return_to_older_value_is_not_duplicate(self):
        self.acquire();new=self.body.replace(b'9.109 383 7139 e-31',b'9.109 383 7138 e-31');self.acquire(new);self.acquire();m=self.stage.monitoring();self.assertEqual(m['observations'][-2]['classification'],'conflict')
    def test_older_source_release_not_correction(self):
        self.acquire();self.acquire(self.body.replace(b'2022 CODATA',b'2018 CODATA').replace(b'9.109 383 7139 e-31',b'9.109 383 7138 e-31'));self.assertEqual(self.stage.monitoring()['counts']['conflict'],1)
    def test_metadata_only_change(self):
        self.acquire();self.acquire(self.body.replace(b'2022 CODATA',b'2024 CODATA'));m=self.stage.monitoring();self.assertEqual(m['counts']['correction'],0);self.assertTrue(m['observations'][-2]['metadata_changed'])
    def test_pubchem_snapshot_not_proof_of_correction(self):
        b=ROOT.parent.joinpath('experiment012/fixtures/pubchem_synthetic.json').read_bytes();self.stage.acquire('pubchem',{'cid':962},transport=self.transport(b));self.stage.acquire('pubchem',{'cid':962},transport=self.transport(b.replace(b'"42"',b'"43"')));m=self.stage.monitoring();self.assertEqual(m['counts']['conflict'],1);self.assertEqual(m['observations'][0]['scientific_classification'],'computed_property');self.assertIsNone(m['observations'][0]['uncertainty']['value'])
    def test_parse_failure_keeps_evidence(self):
        with self.assertRaises(ValueError):self.acquire(b'not a CODATA table')
        self.assertEqual(self.stage.db.execute('SELECT count(*) FROM exchanges').fetchone()[0],1);self.assertEqual(self.stage.db.execute('SELECT count(*) FROM captures').fetchone()[0],1);self.assertEqual(self.stage.monitoring()['sources']['nist']['outcomes']['validation_failed'],1)
    def test_payload_identity_failure(self):
        b=ROOT.parent.joinpath('experiment012/fixtures/pubchem_synthetic.json').read_bytes()
        with self.assertRaises(ValueError):self.stage.acquire('pubchem',{'cid':963},transport=self.transport(b))
        self.assertEqual(self.stage.db.execute('SELECT count(*) FROM observations').fetchone()[0],0)
    def test_mp_no_credential_or_bypass(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(AccessUnavailable):self.stage.acquire('materials_project',{'material_id':'mp-149'})
        self.assertEqual(self.stage.db.execute('SELECT count(*) FROM exchanges').fetchone()[0],0)
    def test_mp_terms_required(self):
        with patch.dict(os.environ,{'MP_API_KEY':'synthetic-test-key'}):
            with self.assertRaises(AccessUnavailable):self.stage.acquire('materials_project',{'material_id':'mp-149'})
    def test_unknown_mp_density(self):
        b=json.loads(ROOT.parent.joinpath('experiment012/fixtures/mp_synthetic.json').read_text());b['data'][0]['density']=None
        with patch.dict(os.environ,{'MP_API_KEY':'synthetic-test-key'}):self.stage.acquire('materials_project',{'material_id':'mp-149','terms_accepted':True},transport=self.transport(json.dumps(b).encode()))
        m=self.stage.monitoring();self.assertEqual(m['counts']['missing'],1);self.assertEqual(m['sources']['materials_project']['coverage_count'],0)
    def test_restart_preserves_evidence(self):
        self.acquire();before=self.stage.monitoring();self.restart();self.assertEqual(self.stage.monitoring(),before);self.assertTrue(self.stage.verify())
    def test_old_staging_refused(self):
        from legacy import Stage
        p=self.root/'012.sqlite';old=Stage(p);old.close();h=hashlib.sha256(p.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):VerificationStage(p)
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),h)
    def test_catalogue_refused(self):
        p=self.root/'catalogue.sqlite';build(p);h=hashlib.sha256(p.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):VerificationStage(p)
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),h)
    def test_append_only_evidence(self):
        self.acquire()
        for table in ['runs','run_results','exchanges','observations']:
            with self.assertRaises(sqlite3.IntegrityError):self.stage.db.execute('DELETE FROM '+table)
    def test_injected_transport_cannot_claim_live(self):
        with self.assertRaises(ValueError):VerifiedTransport(self.stage,opener=lambda *a,**k:FixtureResponse(self.body))
    def test_cache_reuse_and_forced_refresh(self):
        calls=[]
        def op(*a,**k):calls.append(1);return FixtureResponse(self.body)
        t=self.transport(opener=op);self.stage.acquire('nist',transport=t,refresh=False);self.stage.acquire('nist',transport=t,refresh=False);self.assertEqual(len(calls),1);self.stage.acquire('nist',transport=t,refresh=True);self.assertEqual(len(calls),2)
    def test_live_cannot_relabel_synthetic_cache(self):
        self.acquire();t=VerifiedTransport(self.stage,clock=self.clock,sleep=self.sleep)
        def fail(*a,**k):raise urllib.error.URLError('Tunnel connection failed: 403 Forbidden')
        with patch.object(t,'opener',fail):
            with self.assertRaises(AccessUnavailable):self.stage.acquire('nist',transport=t,refresh=False)
        self.assertEqual(self.stage.monitoring()['sources']['nist']['http_success_exchanges'],0)
    def test_hash_corruption_detected(self):
        self.acquire();self.stage.db.execute('DROP TRIGGER no_exchanges_update');self.stage.db.execute("UPDATE exchanges SET sha256='bad'")
        with self.assertRaises(ValueError):self.stage.verify()
    def test_metadata_corruption_detected(self):
        self.acquire();self.stage.db.execute('DROP TRIGGER no_exchanges_update');self.stage.db.execute("UPDATE exchanges SET headers='{}'")
        with self.assertRaises(ValueError):self.stage.verify()
    def test_interrupted_run_recovery(self):
        cur=self.stage.db.execute('INSERT INTO runs(source,query,started,deadline) VALUES (?,?,?,?)',('nist','{}',self.clock(),self.clock()+300));id=cur.lastrowid;self.restart();self.assertEqual(self.stage.recover_interrupted(),[]);self.now[0]+=301;self.assertEqual(self.stage.recover_interrupted(),[id]);self.assertEqual(self.stage.recover_interrupted(),[])
    def test_baseexception_interruption(self):
        def op(*a,**k):raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.stage.acquire('nist',transport=self.transport(opener=op))
        self.restart();self.now[0]+=301;self.assertEqual(len(self.stage.recover_interrupted()),1);self.acquire();self.assertEqual(self.stage.monitoring()['sources']['nist']['outcomes']['success'],1)
    def test_timeout_bounded_retries(self):
        calls=[]
        def op(*a,**k):calls.append(k['timeout']);raise TimeoutError('synthetic-private')
        with self.assertRaises(AccessUnavailable):self.stage.acquire('nist',transport=self.transport(opener=op))
        self.assertEqual(calls,[15,15,15]);self.assertTrue(all(e['outcome']=='timeout' for e in self.stage.monitoring()['exchanges']));self.assertNotIn(b'synthetic-private',self.stage.path.read_bytes())
    def test_retry_success_429(self):
        calls=[]
        def op(*a,**k):
            calls.append(1)
            if len(calls)==1:raise urllib.error.HTTPError(NIST_URL,429,'rate',{'Retry-After':'2'},io.BytesIO(b'rate-limit fixture'))
            return FixtureResponse(self.body)
        start=self.clock();self.stage.acquire('nist',transport=self.transport(opener=op));self.assertEqual(len(calls),2);self.assertGreaterEqual(self.clock()-start,2);m=self.stage.monitoring();self.assertEqual(m['exchanges'][0]['http_status'],429);self.assertEqual(self.stage.db.execute('SELECT body FROM exchanges ORDER BY id LIMIT 1').fetchone()[0],b'rate-limit fixture')
    def test_long_retry_after_deferred(self):
        def op(*a,**k):raise urllib.error.HTTPError(NIST_URL,429,'rate',{'Retry-After':'600'},io.BytesIO(b'fixture'))
        with self.assertRaises(AccessUnavailable):self.stage.acquire('nist',transport=self.transport(opener=op))
        until=self.stage.db.execute('SELECT next_allowed FROM throttle').fetchone()[0];self.assertGreaterEqual(until,self.clock()+600);self.restart();self.assertGreaterEqual(self.stage.db.execute('SELECT next_allowed FROM throttle').fetchone()[0],until)
    def test_http_date_retry_after(self):
        from email.utils import formatdate
        calls=[]
        def op(*a,**k):
            calls.append(1)
            if len(calls)==1:raise urllib.error.HTTPError(NIST_URL,503,'busy',{'Retry-After':formatdate(self.clock()+5,usegmt=True)},io.BytesIO(b'fixture'))
            return FixtureResponse(self.body)
        start=self.clock();self.stage.acquire('nist',transport=self.transport(opener=op));self.assertGreaterEqual(self.clock()-start,5)
    def test_policy_denial_is_not_retried(self):
        calls=[]
        def op(*a,**k):calls.append(1);raise urllib.error.URLError('Tunnel connection failed: 403 Forbidden')
        with self.assertRaises(AccessUnavailable):self.stage.acquire('nist',transport=self.transport(opener=op))
        self.assertEqual(len(calls),1);self.assertEqual(self.stage.monitoring()['exchanges'][0]['outcome'],'destination_policy_denied')
    def test_execution_permission_denial_not_retried(self):
        calls=[]
        def op(*a,**k):calls.append(1);raise urllib.error.URLError(PermissionError('fixture'))
        with self.assertRaises(AccessUnavailable):self.stage.acquire('nist',transport=self.transport(opener=op))
        self.assertEqual(len(calls),1);self.assertEqual(self.stage.monitoring()['exchanges'][0]['outcome'],'execution_permission_denied')
    def test_403_does_not_retry(self):
        calls=[]
        def op(*a,**k):calls.append(1);raise urllib.error.HTTPError(NIST_URL,403,'forbidden',{},io.BytesIO(b'fixture'))
        with self.assertRaises(AccessUnavailable):self.stage.acquire('nist',transport=self.transport(opener=op))
        self.assertEqual(len(calls),1)
    def test_throttle_one_second(self):
        self.acquire();start=self.clock();self.acquire();self.assertGreaterEqual(self.clock()-start,1)
    def test_dynamic_cooldown(self):
        self.stage.acquire('nist',transport=self.transport(opener=lambda *a,**k:FixtureResponse(self.body,{'X-Throttling-Control':'Red'})));self.assertEqual(self.stage.db.execute('SELECT next_allowed FROM throttle').fetchone()[0],self.clock()+60)
    def test_response_size_limit(self):
        with self.assertRaises(AccessUnavailable):self.acquire(b'x'*2_000_001)
        self.assertEqual(self.stage.db.execute('SELECT body FROM exchanges').fetchone()[0],None)
    def test_allowlist(self):
        with self.assertRaises(AccessUnavailable):self.transport().get('nist','https://example.com')
    def test_scheduler_tick_and_no_automatic_publication(self):
        s=VerificationScheduler(self.stage,self.clock);s.add('nist-due','nist',{},60);r=s.tick(lambda source,query,refresh:self.stage.acquire(source,query,refresh,self.transport()),limit=1);self.assertEqual(r[0]['status'],'success');self.assertEqual(s.tick(limit=1),[]);self.assertEqual(self.stage.monitoring()['published_count'],0)
    def test_scheduler_failure_recovery(self):
        s=VerificationScheduler(self.stage,self.clock);s.add('job','nist',{},60)
        def fail(*a,**k):raise TimeoutError('fixture')
        self.assertTrue(s.tick(fail)[0]['status'].startswith('failed'));self.restart();self.now[0]+=61;s=VerificationScheduler(self.stage,self.clock);self.assertEqual(s.tick(lambda *a,**k:[])[0]['status'],'success')
    def test_lease_fences_expired_worker(self):
        s=VerificationScheduler(self.stage,self.clock);s.add('job','nist',{},60);old=s.claim();self.assertIsNone(s.claim());self.now[0]+=301;new=s.claim();self.assertFalse(s.finish(old,'success'));self.assertTrue(s.finish(new,'success'))
    def test_scheduler_secret_query_rejected(self):
        with self.assertRaises(ValueError):VerificationScheduler(self.stage).add('secret','materials_project',{'material_id':'mp-149','api_key':'synthetic'},60)
    def test_live_demo_requires_opt_in(self):
        from live_demo import run
        with self.assertRaises(ValueError):run(self.root/'live')
        self.assertFalse((self.root/'live').exists())
    def test_offline_demo_pins_objects(self):
        from offline_demo import run
        with patch('builtins.print'):r=run(self.root/'demo')
        self.assertTrue(r['all_passed']);self.assertFalse(r['published'])
if __name__=='__main__':unittest.main()
