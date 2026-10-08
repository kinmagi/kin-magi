"""New databases only; append-only repeated observations over unchanged 012 staging."""
import json,sqlite3,time
from pathlib import Path
from legacy import Stage,ROOT,CONNECTORS,validate_record,science,canonical,digest,number,AccessUnavailable
from verified_transport import VerifiedTransport

class VerificationStage(Stage):
    def __init__(self,path,baseline_path=None,clock=time.time):
        path=Path(path).resolve()
        # Do not migrate historical staging or any other existing database.
        if path.exists():
            db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
            try:
                try:ok=db.execute("SELECT value FROM meta WHERE key='verification_schema'").fetchone()==('013.1',)
                except sqlite3.Error:ok=False
            finally:db.close()
            if not ok:raise ValueError('refusing historical/non-013 database; create a fresh staging path')
        super().__init__(path,baseline_path);self.clock=clock;self.active_run=None
        if not self.db.execute("SELECT value FROM meta WHERE key='verification_schema'").fetchone():
            self.db.executescript(ROOT.joinpath('schema.sql').read_text())
            for table in ['runs','run_results','exchanges','observations']:
                for op in ['UPDATE','DELETE']:
                    self.db.execute(f"CREATE TRIGGER no_{table}_{op.lower()} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'immutable verification evidence'); END")
            self.db.execute("INSERT INTO meta VALUES ('verification_schema','013.1')")
    @staticmethod
    def query(source,query):
        if source not in CONNECTORS or not isinstance(query,dict):raise ValueError('unsupported source/query')
        allowed={'nist':set(),'pubchem':{'cid'},'materials_project':{'material_id','terms_accepted'}}[source]
        if set(query)-allowed:raise ValueError('query fields unsupported; never put credentials in query')
        canonical(query)
        if source=='pubchem' and (type(query.get('cid'))!=int or not 1<=query['cid']<=1_000_000_000):raise ValueError('explicit CID required')
        if source=='materials_project':
            import re
            if not re.fullmatch(r'mp-[1-9][0-9]*',query.get('material_id','')):raise ValueError('explicit material ID required')
        return query
    def compare(self,r):
        if r['kind']=='unknown':return 'missing','source value unknown',False
        old=None
        for encoded, in self.db.execute("SELECT record FROM incoming WHERE baseline_hash=? AND classification!='rejected' ORDER BY id DESC",(self.baseline_hash,)):
            x=json.loads(encoded)
            if x.get('key')==r['key']:old=x;break
        if old:
            same=science(old)==science(r);p=r['provenance'];q=old['provenance']
            meta=any(p[k]!=q[k] for k in ['source_version','publication_reference','license','license_status','rights_url'])
            if same:return 'unchanged','matches latest scientific content; source metadata retained',meta
            # Snapshot hashes are not ordered provider releases and do not prove correction.
            newer=(p['source']=='nist' and q['source']=='nist' and p['source_version'].isdigit() and q['source_version'].isdigit() and int(p['source_version'])>int(q['source_version']))
            if newer:return 'correction','newer CODATA release differs; correction candidate requires review',meta
            return 'conflict','different latest content without an established newer ordered source release',meta
        kind,reason=super().classify(r)
        return ('unchanged' if kind=='duplicate' else kind),reason,False
    def classify(self,r):
        kind,reason,_=self.compare(r)
        return ('duplicate' if kind=='unchanged' else kind),reason
    def acquire(self,source,query=None,refresh=True,transport=None):
        query=self.query(source,query or {})
        if self.active_run is not None:raise RuntimeError('one active acquisition per connection')
        start=self.clock();cur=self.db.execute('INSERT INTO runs(source,query,started,deadline) VALUES (?,?,?,?)',(source,canonical(query),start,start+300));run=cur.lastrowid;self.active_run=run
        client=transport or VerifiedTransport(self,clock=self.clock)
        stage=self
        class Capturing:
            def get(self,*args,**kwargs):
                body,headers,e=client.get(*args,**kwargs);stage.capture(body,e);return body,headers,e
        try:
            records=CONNECTORS[source].fetch(Capturing(),query,refresh=refresh)
            # Per-run observations and result are one transaction; exact exchanges/captures already durable.
            self.db.execute('BEGIN IMMEDIATE');ids=[];rejected=False
            try:
                for r in records:
                    try:validate_record(r);self.verify_evidence(r);kind,reason,meta=self.compare(r)
                    except (ValueError,KeyError,TypeError):kind,reason,meta='rejected','independent scientific format/evidence validation failed',False;rejected=True
                    encoded=canonical(r);h=digest({'record':r,'baseline':self.baseline_hash})
                    existing=self.db.execute('SELECT id FROM incoming WHERE hash=?',(h,)).fetchone()
                    if existing:id=existing[0]
                    else:
                        id=self.db.execute('INSERT INTO incoming(record,hash,classification,reason,baseline_hash) VALUES (?,?,?,?,?)',(encoded,h,'duplicate' if kind=='unchanged' else kind,reason,self.baseline_hash)).lastrowid
                    ids.append(id);self.db.execute('INSERT INTO observations(run_id,incoming_id,classification,reason,metadata_changed) VALUES (?,?,?,?,?)',(run,id,kind,reason,int(meta)))
                self.db.execute('INSERT INTO run_results VALUES (?,?,?,?)',(run,self.clock(),'validation_failed' if rejected else 'success','validated observations staged; no promotion' if not rejected else 'some records rejected'))
                self.db.commit()
            except BaseException:self.db.rollback();raise
            if rejected:raise ValueError('staged observations failed independent validation')
            return ids
        except Exception as exc:
            status='access_unavailable' if isinstance(exc,AccessUnavailable) else 'validation_failed'
            safe=str(exc) if isinstance(exc,AccessUnavailable) else type(exc).__name__
            self.db.execute('INSERT OR IGNORE INTO run_results VALUES (?,?,?,?)',(run,self.clock(),status,safe));raise
        finally:self.active_run=None
    def recover_interrupted(self):
        rows=self.db.execute('SELECT id FROM runs WHERE deadline<=? AND id NOT IN (SELECT run_id FROM run_results)',(self.clock(),)).fetchall()
        for id, in rows:self.db.execute('INSERT OR IGNORE INTO run_results VALUES (?,?,?,?)',(id,self.clock(),'interrupted','expired acquisition; evidence retained; reacquire through a fresh run'))
        return [x[0] for x in rows]
    def verify(self):
        import hashlib
        if self.db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or self.db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('staging integrity failure')
        for body,h in self.db.execute('SELECT body,sha256 FROM exchanges WHERE body IS NOT NULL'):
            if hashlib.sha256(body).hexdigest()!=h:raise ValueError('exchange hash mismatch')
        for run,source,url,utc,status,h,headers,outcome,origin,evidence_hash in self.db.execute('SELECT run_id,source,url,utc,status,sha256,headers,outcome,origin,evidence_hash FROM exchanges'):
            metadata={'run':run,'source':source,'url':url,'utc':utc,'status':status,'sha256':h,'headers':json.loads(headers),'outcome':outcome,'origin':origin}
            if digest(metadata)!=evidence_hash:raise ValueError('exchange metadata integrity failure')
        for record, in self.db.execute("SELECT record FROM incoming WHERE classification!='rejected'"):
            r=validate_record(json.loads(record));self.verify_evidence(r)
        return True
    def monitoring(self):
        self.recover_interrupted();sources={}
        for source in CONNECTORS:
            results=list(self.db.execute('SELECT rr.status,rr.reason,r.started,rr.finished FROM runs r JOIN run_results rr ON r.id=rr.run_id WHERE r.source=? ORDER BY r.id',(source,)))
            counts={k:sum(r[0]==k for r in results) for k in ['success','access_unavailable','validation_failed','interrupted']}
            coverage=list(self.db.execute("SELECT DISTINCT i.record FROM incoming i JOIN observations o ON o.incoming_id=i.id JOIN runs r ON r.id=o.run_id WHERE r.source=? AND o.classification NOT IN ('rejected','missing')",(source,)))
            keys=sorted({json.loads(x[0])['key'] for x in coverage});live=self.db.execute("SELECT count(*) FROM exchanges e JOIN runs r ON r.id=e.run_id WHERE r.source=? AND e.outcome='http_success' AND e.origin='live'",(source,)).fetchone()[0]
            sources[source]={'completed_runs':len(results),'outcomes':counts,'success_fraction':counts['success']/len(results) if results else None,'http_success_exchanges':live,'last_result':results[-1][0] if results else None,'last_error':next((r[1] for r in reversed(results) if r[0]!='success'),None),'distinct_staged_keys':keys,'coverage_count':len(keys)}
        observations=[]
        for id,run,record,kind,reason,meta in self.db.execute('SELECT o.id,o.run_id,i.record,o.classification,o.reason,o.metadata_changed FROM observations o JOIN incoming i ON i.id=o.incoming_id ORDER BY o.id'):
            r=json.loads(record);p=r.get('provenance',{});scientific='reference_constant' if p.get('source')=='nist' else {'calculated':'computed_property','measured':'experimental_measurement','unknown':'unknown','estimated':'estimated_property','exact':'exact_definition'}.get(r.get('kind'),'unknown')
            observations.append({'id':id,'run':run,'key':r.get('key'),'classification':kind,'reason':reason,'metadata_changed':bool(meta),'scientific_classification':scientific,'legacy_kind':r.get('kind'),'evidence_origin':p.get('capture'),'source_version':p.get('source_version'),'units':r.get('units'),'conditions':r.get('conditions'),'uncertainty':r.get('uncertainty'),'unknown_information':(['publication_details','measurement_uncertainty','experimental_temperature','experimental_pressure'] if p.get('source') in {'pubchem','materials_project'} else [] )})
        pending=sorted({x['key'] for x in observations if x['classification'] in {'new','correction','conflict'}})
        exchanges=[{'id':id,'run':run,'source':source,'url':url,'retrieved_at':utc,'http_status':status,'sha256':h,'headers':json.loads(headers),'source_response_date':json.loads(headers).get('date'),'source_last_modified':json.loads(headers).get('last-modified'),'outcome':outcome,'origin':origin} for id,run,source,url,utc,status,h,headers,outcome,origin in self.db.execute('SELECT id,run_id,source,url,utc,status,sha256,headers,outcome,origin FROM exchanges ORDER BY id')]
        return {'exchanges':exchanges,'schema':'013.monitor.1','baseline_version':self.baseline['version'],'baseline_hash':self.baseline_hash,'sources':sources,'observations':observations,'pending_review_keys':pending,
            'counts':{k:sum(x['classification']==k for x in observations) for k in ['new','unchanged','correction','conflict','missing','rejected']},
            'unfinished_runs':self.db.execute('SELECT count(*) FROM runs WHERE id NOT IN (SELECT run_id FROM run_results)').fetchone()[0],
            'candidate_count':self.db.execute('SELECT count(*) FROM candidates').fetchone()[0],'approved_count':self.db.execute('SELECT count(*) FROM approvals').fetchone()[0],
            'published_count':self.db.execute('SELECT count(*) FROM publications').fetchone()[0],'meaning':'Staged coverage and accepted format do not establish authoritative scientific coverage or licence approval.'}
