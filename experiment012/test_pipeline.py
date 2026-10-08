import copy,hashlib,io,json,os,sqlite3,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
from compat import ROOT,build,Catalog,digest
from pipeline import Stage,validate_record,science
from connectors import NIST,PubChem,MaterialsProject,NIST_URL,PUBCHEM_ROOT,allowed_url
from scheduler import Scheduler
from transport import Transport,AccessUnavailable

class Response:
    headers={'Content-Type':'text/plain','Authorization':'must-not-be-cached'}
    def __init__(self,body):self.body=body
    def read(self,limit):return self.body[:limit]
    def __enter__(self):return self
    def __exit__(self,*args):pass

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.stage=Stage(self.root/'stage.sqlite')
        self.body=ROOT.joinpath('fixtures/nist_excerpt.txt').read_bytes();self.evidence=json.loads(ROOT.joinpath('fixtures/nist_excerpt_metadata.json').read_text())
        self.records=NIST().parse(self.body,self.evidence)
        self.stage.capture(self.body,self.evidence)
    def tearDown(self):self.stage.close();self.tmp.cleanup()
    def candidate(self):
        id=self.stage.ingest([self.records[0]])[0];return self.stage.candidate([id],'cw012-test.1')
    def test_source_traceability(self):
        r=validate_record(self.records[0]);self.assertEqual(r['provenance']['raw_sha256'],hashlib.sha256(self.body).hexdigest());self.assertEqual(r['value'],'9.1093837139E-31');self.assertEqual(r['uncertainty']['value'],'2.8E-40');self.assertEqual(r['provenance']['source_version'],'2022')
    def test_unknown_units_rejected(self):
        r=copy.deepcopy(self.records[0]);r['units']='bananas';id=self.stage.ingest([r])[0];self.assertEqual(self.stage.review()['records'][0]['classification'],'rejected')
    def test_dimension_mismatch(self):
        r=copy.deepcopy(self.records[0]);r['units']='K'
        with self.assertRaises(ValueError):validate_record(r)
    def test_uncertainty_dimensions(self):
        r=copy.deepcopy(self.records[0]);r['uncertainty']['units']='s'
        with self.assertRaises(ValueError):validate_record(r)
    def test_conditions(self):
        r=copy.deepcopy(self.records[0]);r['conditions']['temperature_K']=['300','200']
        with self.assertRaises(ValueError):validate_record(r)
    def test_provenance_missing(self):
        r=copy.deepcopy(self.records[0]);del r['provenance']['publication_reference']
        with self.assertRaises(ValueError):validate_record(r)
    def test_identity_mismatch(self):
        r=copy.deepcopy(self.records[0]);r['subject']['id']='m_u'
        with self.assertRaises(ValueError):validate_record(r)
    def test_nan_rejected(self):
        r=copy.deepcopy(self.records[0]);r['value']='NaN'
        with self.assertRaises(ValueError):validate_record(r)
    def test_new_and_baseline_duplicate(self):
        self.stage.ingest(self.records);self.assertEqual(self.stage.review()['counts']['new'],1);self.assertEqual(self.stage.review()['counts']['duplicate'],1)
    def test_idempotent_ingest(self):
        ids=self.stage.ingest(self.records);self.assertEqual(ids,self.stage.ingest(self.records));self.assertEqual(len(self.stage.review()['records']),2)
    def test_retrieval_time_is_not_change(self):
        r=copy.deepcopy(self.records[0]);self.stage.ingest([r]);r['provenance']['retrieved_at']+=1;self.stage.ingest([r]);self.assertEqual(self.stage.review()['counts']['duplicate'],1)
    def test_unit_normalization(self):
        r=copy.deepcopy(self.records[0]);r['units']='g';r['value']='9.1093837139e-28';r['uncertainty']['units']='g';r['uncertainty']['value']='2.8e-37';self.assertEqual(science(r),science(self.records[0]))
    def test_conflict_detected(self):
        self.stage.ingest([self.records[0]]);r=copy.deepcopy(self.records[0]);r['value']='1e-30';self.stage.ingest([r]);self.assertEqual(self.stage.review()['counts']['conflict'],1)
    def test_correction_requires_resolution(self):
        self.stage.ingest([self.records[0]]);r=copy.deepcopy(self.records[0]);r['value']='1e-30';r['provenance']['source_version']='synthetic-next';r['provenance']['capture']='synthetic_fixture';id=self.stage.ingest([r])[0]
        self.assertEqual(self.stage.review()['counts']['correction'],1)
        with self.assertRaises(ValueError):self.stage.candidate([id],'cw012-resolution.1')
        with self.assertRaises(ValueError):self.stage.candidate([id],'cw012-resolution.1',{str(id):'Synthetic resolution cannot override source capture'})
    def test_unknown_property(self):
        e={**self.evidence,'url':'https://api.materialsproject.org/materials/summary/?material_ids=mp-149','mode':'synthetic_fixture'}
        b=json.loads(ROOT.joinpath('fixtures/mp_synthetic.json').read_text());b['data'][0]['density']=None
        r=MaterialsProject().parse(json.dumps(b).encode(),e,'mp-149');self.stage.ingest(r);self.assertEqual(self.stage.review()['counts']['missing'],1)
    def test_pubchem_is_calculated_and_unresolved(self):
        e={**self.evidence,'url':PUBCHEM_ROOT+'962/property/MolecularFormula,MolecularWeight/JSON','mode':'synthetic_fixture'}
        r=PubChem().parse(ROOT.joinpath('fixtures/pubchem_synthetic.json').read_bytes(),e,962)[0]
        validate_record(r);self.assertEqual(r['kind'],'calculated');id=self.stage.ingest([r])[0]
        with self.assertRaises(ValueError):self.stage.candidate([id],'cw012-no-mapping.1')
        with self.assertRaises(ValueError):PubChem().parse(ROOT.joinpath('fixtures/pubchem_synthetic.json').read_bytes(),e,963)
    def test_mp_credentials_and_terms_gate(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(AccessUnavailable):MaterialsProject().fetch(None,{'material_id':'mp-149'})
        with patch.dict(os.environ,{'MP_API_KEY':'synthetic-not-a-real-key'}):
            with self.assertRaises(AccessUnavailable):MaterialsProject().fetch(None,{'material_id':'mp-149'})
    def test_mp_fixture_classification(self):
        e={**self.evidence,'url':'https://api.materialsproject.org/materials/summary/?material_ids=mp-149','mode':'synthetic_fixture'}
        r=MaterialsProject().parse(ROOT.joinpath('fixtures/mp_synthetic.json').read_bytes(),e,'mp-149')[0];validate_record(r);self.assertEqual(r['kind'],'calculated');self.assertIsNone(r['conditions']['temperature_K'])
    def test_rejected_not_candidate(self):
        r=copy.deepcopy(self.records[0]);r['units']='bogus';id=self.stage.ingest([r])[0]
        with self.assertRaises(ValueError):self.stage.candidate([id],'cw012-invalid.1')
    def test_candidate_restart(self):
        c=self.candidate();path=self.stage.path;self.stage.close();self.stage=Stage(path);self.assertEqual(self.stage.load_candidate(c['hash'])['manifest'],c['manifest'])
    def test_unsubstantiated_value_cannot_enter_candidate(self):
        r=copy.deepcopy(self.records[0]);r['value']='1e-30';id=self.stage.ingest([r])[0]
        with self.assertRaises(ValueError):self.stage.candidate([id],'cw012-unsubstantiated.1')
    def test_capture_is_immutable(self):
        with self.assertRaises(sqlite3.IntegrityError):self.stage.db.execute("UPDATE captures SET body=X'00'")
    def test_synthetic_publication_rejected(self):
        e={**self.evidence,'mode':'synthetic_fixture'};self.stage.capture(self.body,e);r=NIST().parse(self.body,e)[0];id=self.stage.ingest([r])[0];c=self.stage.candidate([id],'cw012-synthetic.1')
        with self.assertRaises(ValueError):self.stage.approve(c['hash'],'test reviewer','test only',licenses_reviewed=True)
    def test_candidate_immutable(self):
        c=self.candidate()
        with self.assertRaises(sqlite3.IntegrityError):self.stage.db.execute('UPDATE candidates SET record=? WHERE hash=?',('{}',c['hash']))
    def test_unapproved_publication(self):
        c=self.candidate()
        with self.assertRaises(ValueError):self.stage.publish(c['hash'],self.root/'releases')
        self.assertFalse((self.root/'releases').exists())
    def test_approval_licence_gate(self):
        c=self.candidate()
        with self.assertRaises(ValueError):self.stage.approve(c['hash'],'test reviewer','test evidence')
        self.assertEqual(self.stage.db.execute('SELECT count(*) FROM approvals').fetchone()[0],0)
    def test_approved_test_release_preserves_old(self):
        old=self.root/'old.sqlite';build(old);before=hashlib.sha256(old.read_bytes()).hexdigest();c=self.candidate()
        # Only temporary test directories; this does not approve any delivered candidate.
        self.stage.approve(c['hash'],'unit-test reviewer','Temporary publication gate test; not project approval',licenses_reviewed=True)
        self.stage.publish(c['hash'],self.root/'releases');path=self.root/'releases'/c['version']
        self.assertTrue((path/'READY').exists());cat=Catalog(path/'catalog.sqlite');self.assertEqual(cat.constant('electron_mass',c['version'])['value'],'9.1093837139E-31');cat.close()
        with self.assertRaises(FileExistsError):self.stage.publish(c['hash'],self.root/'releases')
        self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(),before)
    def test_baseline_change_invalidates_candidate(self):
        baseline=self.root/'baseline.json';data=copy.deepcopy(self.stage.baseline);baseline.write_text(json.dumps(data));other=Stage(self.root/'other.sqlite',baseline);other.capture(self.body,self.evidence);id=other.ingest([self.records[0]])[0];c=other.candidate([id],'cw012-pinned.1');other.close();data['version']='changed-baseline';baseline.write_text(json.dumps(data));other=Stage(self.root/'other.sqlite',baseline)
        try:
            with self.assertRaises(ValueError):other.load_candidate(c['hash'])
        finally:other.close()
    def test_existing_catalog_is_not_staging(self):
        p=self.root/'catalog.sqlite';build(p);before=hashlib.sha256(p.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):Stage(p)
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),before)
    def test_transport_allowlist(self):
        self.assertFalse(allowed_url('nist','https://example.com'))
        with self.assertRaises(AccessUnavailable):Transport(self.stage).get('nist','https://example.com')
    def test_cache_restart_and_secret_exclusion(self):
        count=[];op=lambda *a,**k:(count.append(1) or Response(self.body));t=Transport(self.stage,opener=op)
        t.get('nist',NIST_URL,headers={'X-API-KEY':'synthetic-secret'});path=self.stage.path;self.stage.close();self.stage=Stage(path)
        b,h,e=Transport(self.stage,opener=op).get('nist',NIST_URL);self.assertEqual(len(count),1);self.assertEqual(e['mode'],'cache');self.assertNotIn('authorization',h);self.assertNotIn(b'synthetic-secret',path.read_bytes())
    def test_cache_corruption(self):
        t=Transport(self.stage,opener=lambda *a,**k:Response(self.body));t.get('nist',NIST_URL);self.stage.db.execute("UPDATE responses SET body=X'00'")
        with self.assertRaises(AccessUnavailable):t.get('nist',NIST_URL)
    def test_retry_and_throttle(self):
        now=[1000.];waits=[];calls=[]
        def sleep(d):waits.append(d);now[0]+=d
        def op(*a,**k):
            calls.append(1)
            if len(calls)==1:raise urllib.error.HTTPError(NIST_URL,429,'rate',{'Retry-After':'2'},None)
            return Response(self.body)
        Transport(self.stage,opener=op,clock=lambda:now[0],sleep=sleep).get('nist',NIST_URL)
        self.assertEqual(len(calls),2);self.assertIn(2,waits);self.assertEqual(self.stage.db.execute('SELECT count(*) FROM attempts').fetchone()[0],2)
    def test_long_retry_after_is_persisted(self):
        def op(*a,**k):raise urllib.error.HTTPError(NIST_URL,429,'rate',{'Retry-After':'120'},None)
        with self.assertRaises(AccessUnavailable):Transport(self.stage,opener=op,clock=lambda:1000.,sleep=lambda d:None).get('nist',NIST_URL)
        self.assertEqual(self.stage.db.execute('SELECT next_allowed FROM throttle').fetchone()[0],1120.)
    def test_dynamic_throttle_cooldown(self):
        response=Response(self.body);response.headers={'X-Throttling-Control':'Request Count status: Red (90%)'}
        Transport(self.stage,opener=lambda *a,**k:response,clock=lambda:1000.).get('nist',NIST_URL)
        self.assertEqual(self.stage.db.execute('SELECT next_allowed FROM throttle').fetchone()[0],1060.)
    def test_auth_failure_not_retried(self):
        calls=[]
        def op(*a,**k):calls.append(1);raise urllib.error.HTTPError(NIST_URL,403,'auth',{},None)
        with self.assertRaises(AccessUnavailable):Transport(self.stage,opener=op).get('nist',NIST_URL)
        self.assertEqual(len(calls),1)
    def test_bounded_network_retries(self):
        calls=[]
        def op(*a,**k):calls.append(1);raise urllib.error.URLError('synthetic-secret-url')
        with self.assertRaises(AccessUnavailable):Transport(self.stage,opener=op,sleep=lambda d:None).get('nist',NIST_URL)
        self.assertEqual(len(calls),3);self.assertNotIn(b'synthetic-secret-url',self.stage.path.read_bytes())
    def test_scheduler_restart_failure_recovery(self):
        now=[1000.];s=Scheduler(self.stage,lambda:now[0]);s.add('daily','nist',{},86400)
        def fail(*a,**k):raise AccessUnavailable('fixture')
        self.assertTrue(s.tick(fail)[0]['result'].startswith('failed'))
        self.assertEqual(s.tick(lambda *a,**k:[]),[]);now[0]+=301
        path=self.stage.path;self.stage.close();self.stage=Stage(path);s=Scheduler(self.stage,lambda:now[0]);self.assertEqual(s.tick(lambda *a,**k:[1])[0]['result'],'success');self.assertEqual(self.stage.db.execute('SELECT count(*) FROM approvals').fetchone()[0],0)
    def test_scheduler_lease_recovery(self):
        s=Scheduler(self.stage,lambda:1000.);s.add('due','nist',{},60);self.stage.db.execute('UPDATE jobs SET lease_until=1300');self.assertEqual(s.tick(lambda *a,**k:[]),[]);s=Scheduler(self.stage,lambda:1301.);self.assertEqual(len(s.tick(lambda *a,**k:[])),1)
    def test_scheduler_credential_queries_rejected(self):
        with self.assertRaises(ValueError):Scheduler(self.stage).add('secret','materials_project',{'api_key':'synthetic'},86400)
    def test_demo_preserves_world_and_lab(self):
        from demo import run
        with patch('builtins.print'):r=run(self.root/'demo')
        self.assertTrue(r['all_passed']);self.assertFalse(r['published'])
if __name__=='__main__':unittest.main()
