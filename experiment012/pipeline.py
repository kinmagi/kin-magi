"""Separate acquisition staging and human-reviewed immutable release construction."""
import copy,hashlib,json,re,sqlite3,time
from pathlib import Path
from datetime import datetime,timezone
from compat import canonical,digest,number,unit,validate_manifest,build,Catalog,ROOT
from connectors import CONNECTORS,allowed_url,POLICIES
from transport import Transport

EXTRA_UNITS={'g/mol':((1,0,0,0,-1,0),'0.001')}
def dimensions(name):return EXTRA_UNITS[name][0] if name in EXTRA_UNITS else unit(name)[0]

def validate_record(r):
    if set(r)!={'schema','key','subject','property','value','units','kind','conditions','uncertainty','provenance'} or r['schema']!=1:raise ValueError('record schema mismatch')
    canonical(r)
    if not isinstance(r['key'],str) or not r['key'] or not isinstance(r['subject'],dict) or not r['subject'].get('id'):raise ValueError('identity missing')
    if r['kind'] not in {'measured','calculated','estimated','unknown','exact'}:raise ValueError('scientific classification missing')
    expected={'electron_mass':'kg','m_u':'kg','density':'g/cm3','molecular_weight':'g/mol'}
    if r['property'] not in expected or dimensions(r['units'])!=dimensions(expected[r['property']]):raise ValueError('unsupported property or dimensions')
    s=r['subject']
    if r['property'] in {'electron_mass','m_u'}:
        if s!={'type':'constant','id':r['property']} or r['key']!='constant:'+r['property']:raise ValueError('constant identity mismatch')
    elif r['property']=='molecular_weight':
        if s.get('namespace')!='PubChem CID' or not re.fullmatch(r'[1-9][0-9]*',s['id']) or not s.get('formula') or r['key']!='pubchem:'+s['id']+':molecular_weight':raise ValueError('compound identity mismatch')
    elif s.get('namespace')!='Materials Project' or not re.fullmatch(r'mp-[1-9][0-9]*',s['id']) or not s.get('formula') or r['key']!='mp:'+s['id']+':density':raise ValueError('crystal identity mismatch')
    if r['kind']=='unknown':
        if r['value'] is not None:raise ValueError('unknown record contains a value')
    elif r['value'] is None or number(r['value'])<=0:raise ValueError('positive finite scientific value required')
    c=r['conditions']
    if not isinstance(c,dict) or not c.get('scope'):raise ValueError('applicable conditions missing')
    for axis in ['temperature_K','pressure_Pa']:
        if axis in c and c[axis] is not None:
            vals=c[axis] if isinstance(c[axis],list) else [c[axis]]
            if len(vals) not in {1,2} or any(number(x)<=0 for x in vals) or (len(vals)==2 and number(vals[0])>number(vals[1])):raise ValueError('invalid condition range')
    u=r['uncertainty']
    if set(u)!={'value','units','kind','note'} or not u['note'] or dimensions(u['units'])!=dimensions(r['units']):raise ValueError('uncertainty metadata or dimensions invalid')
    if u['kind'] not in {'standard','exact','unknown','reported','fit_error'}:raise ValueError('uncertainty classification unsupported')
    if u['value'] is not None and number(u['value'])<0:raise ValueError('negative uncertainty')
    if u['kind']=='unknown' and u['value'] is not None:raise ValueError('unknown uncertainty has a value')
    if u['kind']!='unknown' and u['value'] is None:raise ValueError('reported uncertainty missing')
    if r['kind']=='exact' and (u['kind']!='exact' or number(u['value'])!=0):raise ValueError('exact constant requires zero uncertainty')
    p=r['provenance'];source=p.get('source')
    if source not in CONNECTORS or not allowed_url(source,p.get('url','')):raise ValueError('untrusted source endpoint')
    if not all(p.get(k) for k in ['source_version','publication_reference','license','rights_url','capture']):raise ValueError('source traceability missing')
    if p['rights_url']!=POLICIES[source]['rights_url'] or p['license_status'] not in {'review_required','unresolved'}:raise ValueError('licensing metadata invalid')
    if not re.fullmatch('[0-9a-f]{64}',p.get('raw_sha256','')) or number(p['retrieved_at'])<=0:raise ValueError('retrieval evidence missing')
    if p['capture'] not in {'live','cache','browser_excerpt','synthetic_fixture'}:raise ValueError('unsupported evidence origin')
    if source=='nist' and (r['property'] not in {'electron_mass','m_u'} or r['kind'] not in {'measured','exact'}):raise ValueError('source/property mismatch')
    if source=='pubchem' and (r['property']!='molecular_weight' or r['kind']!='calculated'):raise ValueError('PubChem computed descriptor misclassified')
    if source=='materials_project' and (r['property']!='density' or r['kind'] not in {'calculated','unknown'}):raise ValueError('MP computed density misclassified')
    return r

def science(r):
    """Normalize supported units before comparing; acquisition time is not a scientific change."""
    v=copy.deepcopy({k:r[k] for k in ['subject','property','value','units','kind','conditions','uncertainty']})
    target={'electron_mass':'kg','m_u':'kg','density':'g/cm3','molecular_weight':'g/mol'}[r['property']]
    if r['units'] not in EXTRA_UNITS:
        if v['value'] is not None:v['value']=str(number(v['value']) if r['units']==target else __import__('compat').convert(v['value'],r['units'],target))
        if v['uncertainty']['value'] is not None:v['uncertainty']['value']=str(__import__('compat').convert(v['uncertainty']['value'],v['uncertainty']['units'],target,uncertainty=True))
    elif v['value'] is not None:v['value']=str(number(v['value']))
    v['units']=target;v['uncertainty']['units']=target
    # Decimal canonical numeric equality (1.0 and 1 compare equally).
    for field in [v,v['uncertainty']]:
        if field['value'] is not None:field['value']=str(number(field['value']).normalize())
    return v

class Stage:
    def __init__(self,path,baseline_path=None):
        self.path=Path(path).resolve();self.baseline_path=Path(baseline_path or ROOT.parent/'experiment011'/'dataset.json').resolve()
        self.baseline=validate_manifest(json.loads(self.baseline_path.read_text()));self.baseline_hash=digest(self.baseline)
        if self.path==self.baseline_path:raise ValueError('staging cannot alias baseline')
        self.db=sqlite3.connect(self.path,timeout=10,isolation_level=None)
        self.db.execute('PRAGMA synchronous=FULL');self.db.execute('PRAGMA foreign_keys=ON')
        tables={x[0] for x in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not tables:
            self.db.executescript(ROOT.joinpath('schema.sql').read_text());self.db.execute('INSERT INTO meta VALUES (?,?)',('schema','012.1'))
        elif 'meta' not in tables:
            self.db.close();raise ValueError('refusing non-staging database')
        if self.db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()!=('012.1',):self.db.close();raise ValueError('unsupported staging schema')
    def close(self):self.db.close()
    def ingest(self,records):
        ids=[]
        self.db.execute('BEGIN IMMEDIATE')
        try:
            for record in records:
                encoded=canonical(record);h=digest({'record':record,'baseline':self.baseline_hash})
                old=self.db.execute('SELECT id FROM incoming WHERE hash=?',(h,)).fetchone()
                if old:ids.append(old[0]);continue
                try:
                    validate_record(record);classification,reason=self.classify(record)
                except (ValueError,KeyError,TypeError) as exc:classification,reason='rejected',str(exc)
                cur=self.db.execute('INSERT INTO incoming(record,hash,classification,reason,baseline_hash) VALUES (?,?,?,?,?)',(encoded,h,classification,reason,self.baseline_hash));ids.append(cur.lastrowid)
            self.db.commit()
        except BaseException:self.db.rollback();raise
        return ids
    def classify(self,r):
        if r['kind']=='unknown':return 'missing','value not provided by source'
        existing=[json.loads(x[0]) for x in self.db.execute("SELECT record FROM incoming WHERE baseline_hash=? AND classification!='rejected'",(self.baseline_hash,))]
        matched=[x for x in existing if x.get('key')==r['key']]
        for x in matched:
            if science(x)==science(r):return 'duplicate','same scientific content; provenance retained'
        if matched:
            p=r['provenance'];old=matched[-1]['provenance']
            if old['source']==p['source'] and old['source_version']!=p['source_version']:return 'correction','same source changed content/version; human confirmation required'
            return 'conflict','same scientific key has incompatible content; no winner selected'
        if r['key'].startswith('constant:'):
            baseline=next((x for x in self.baseline['constants'] if 'constant:'+x['id']==r['key']),None)
            if baseline:
                same=(number(baseline['value'])==number(r['value']) and baseline['units']==r['units'] and number(baseline['uncertainty']['value'])==number(r['uncertainty']['value']))
                return ('duplicate','matches previous authoritative constant') if same else ('correction','differs from baseline constant; review conditions, units and source release')
        return 'new','new local reference coverage; not proof of a historical source revision'
    def capture(self,body,evidence):
        if hashlib.sha256(body).hexdigest()!=evidence['sha256']:raise ValueError('capture hash mismatch')
        minimal={k:evidence[k] for k in ['url','retrieved_at','sha256','mode']}
        self.db.execute('INSERT OR IGNORE INTO captures VALUES (?,?,?)',(digest(minimal),body,canonical(minimal)))
    def verify_evidence(self,r):
        p=r['provenance'];e={'url':p['url'],'retrieved_at':p['retrieved_at'],'sha256':p['raw_sha256'],'mode':p['capture']}
        row=self.db.execute('SELECT body,evidence FROM captures WHERE id=?',(digest(e),)).fetchone()
        if not row or hashlib.sha256(row[0]).hexdigest()!=p['raw_sha256'] or json.loads(row[1])!=e:raise ValueError('archived source capture missing or corrupt')
        connector=CONNECTORS[p['source']]
        if p['source']=='nist':parsed=connector.parse(row[0],e)
        elif p['source']=='pubchem':parsed=connector.parse(row[0],e,int(r['subject']['id']))
        else:parsed=connector.parse(row[0],e,r['subject']['id'])
        if canonical(r) not in [canonical(x) for x in parsed]:raise ValueError('proposed value does not match independently re-parsed source capture')
    def acquire(self,source,query=None,refresh=False,transport=None):
        if source not in CONNECTORS:raise ValueError('unsupported connector')
        client=transport or Transport(self)
        stage=self
        class CapturingClient:
            def get(self,*args,**kwargs):
                body,headers,evidence=client.get(*args,**kwargs);stage.capture(body,evidence);return body,headers,evidence
        return self.ingest(CONNECTORS[source].fetch(CapturingClient(),query or {},refresh=refresh))
    def review(self):
        items=[]
        for id,encoded,h,kind,reason,base in self.db.execute('SELECT * FROM incoming ORDER BY id'):
            r=json.loads(encoded);items.append({'id':id,'hash':h,'key':r.get('key'),'classification':kind,'reason':reason,'baseline_hash':base,
                'accepted_format':kind!='rejected','missing_metadata':[k for k in ['uncertainty','provenance'] if not r.get(k)],
                'unknown_fields':(['measurement_uncertainty'] if r.get('uncertainty',{}).get('value') is None else [])+[axis for axis,value in r.get('conditions',{}).items() if value is None]+(['publication_reference_detail'] if r.get('provenance',{}).get('source') in {'pubchem','materials_project'} else []),
                'publication_blockers':(['synthetic fixture'] if r.get('provenance',{}).get('capture')=='synthetic_fixture' else [])+(['licence review required'] if r.get('provenance',{}).get('license_status')!='approved' else [])+(['011 mapping unsupported'] if r.get('subject',{}).get('type')!='constant' else [])})
        return {'baseline_hash':self.baseline_hash,'counts':{k:sum(x['classification']==k for x in items) for k in ['new','duplicate','correction','conflict','missing','rejected']},'records':items,'meaning':'Accepted format is not scientific certification or publication approval.'}
    def candidate(self,ids,version,resolutions=None):
        if not re.fullmatch(r'cw012-[A-Za-z0-9._-]+',version) or version==self.baseline['version']:raise ValueError('new release version required')
        if not ids or len(ids)!=len(set(ids)):raise ValueError('nonempty unique candidate selection required')
        selected=[];resolutions=resolutions or {};keys=set()
        for id in ids:
            row=self.db.execute('SELECT record,classification,baseline_hash FROM incoming WHERE id=?',(id,)).fetchone()
            if not row or row[2]!=self.baseline_hash or row[1] in {'rejected','missing','duplicate'}:raise ValueError('candidate needs actionable validated records from this baseline')
            r=validate_record(json.loads(row[0]))
            if r['key'] in keys:raise ValueError('candidate contains competing keys')
            keys.add(r['key'])
            if row[1] in {'correction','conflict'} and not resolutions.get(str(id)):raise ValueError('explicit documented resolution required')
            if r['subject']['type']!='constant' or r['units']!='kg':raise ValueError('011 export mapping only supports selected kg constants')
            self.verify_evidence(r)
            selected.append(r)
        manifest=self._manifest(selected,version)
        result={'schema':'012.candidate.1','status':'candidate_not_authoritative','baseline_hash':self.baseline_hash,'version':version,
                'manifest':manifest,'selected_records':selected,'resolutions':resolutions,'record_ids':ids}
        h=digest(result)
        self.db.execute('INSERT OR IGNORE INTO candidates VALUES (?,?,?)',(h,canonical(result),time.time()))
        return {'hash':h,**result}
    def _manifest(self,records,version):
        manifest=copy.deepcopy(self.baseline);manifest['version']=version
        for r in records:
            p=r['provenance'];source_id='acquired-'+digest(p)[:24]
            new_source={'id':source_id,'title':'NIST CODATA '+p['source_version'],'url':p['url'],
                'accessed':datetime.fromtimestamp(p['retrieved_at'],timezone.utc).date().isoformat(),'release':p['source_version'],
                'rights':p['license'],'rights_url':p['rights_url'],'reference':p['publication_reference'],
                'verification':'Acquisition evidence '+p['raw_sha256']+'; capture '+p['capture']+'; release requires separate human approval','acquisition':p}
            if not any(x['id']==source_id for x in manifest['sources']):manifest['sources'].append(new_source)
            c={'id':r['subject']['id'],'source_id':source_id,'value':r['value'],'units':r['units'],
               'status':'exact_definition' if r['kind']=='exact' else 'reference_measurement','conditions':r['conditions'],'uncertainty':r['uncertainty']}
            manifest['constants']=[x for x in manifest['constants'] if x['id']!=c['id']]+[c]
        return validate_manifest(manifest)
    def load_candidate(self,h):
        row=self.db.execute('SELECT record FROM candidates WHERE hash=?',(h,)).fetchone()
        if not row:raise ValueError('unknown candidate')
        c=json.loads(row[0])
        if digest(c)!=h or c['baseline_hash']!=self.baseline_hash or digest(self._manifest(c['selected_records'],c['version']))!=digest(c['manifest']):raise ValueError('candidate or baseline integrity failure')
        if len(c['record_ids'])!=len(c['selected_records']):raise ValueError('candidate length mismatch')
        for id,r in zip(c['record_ids'],c['selected_records']):
            staged=self.db.execute('SELECT record FROM incoming WHERE id=?',(id,)).fetchone()
            if not staged or canonical(r)!=staged[0]:raise ValueError('candidate/staging mismatch')
            validate_record(r);self.verify_evidence(r)
        validate_manifest(c['manifest']);return c
    def approve(self,h,reviewer,evidence,*,licenses_reviewed=False):
        """Human-operated API/CLI only. No automatic caller in acquisition or scheduler.
        This records declared approval, not authenticated reviewer identity.
        """
        c=self.load_candidate(h)
        if not reviewer.strip() or not evidence.strip() or licenses_reviewed is not True:raise ValueError('explicit reviewer, approval evidence and licensing review required')
        for r in c['selected_records']:
            if r['provenance']['capture']=='synthetic_fixture' or r['provenance']['license_status']=='unresolved':raise ValueError('synthetic/unlicensed data cannot be published')
        self.db.execute('INSERT INTO approvals VALUES (?,?,?,?)',(h,reviewer,evidence,time.time()))
    def publish(self,h,releases_dir):
        c=self.load_candidate(h);approval=self.db.execute('SELECT reviewer,evidence,approved FROM approvals WHERE candidate_hash=?',(h,)).fetchone()
        if not approval:raise ValueError('explicit approval required before publication')
        root=Path(releases_dir).resolve();root.mkdir(parents=True,exist_ok=True);target=root/c['version']
        # Exclusive new directory; recovery never overwrites a partially constructed release.
        target.mkdir()
        try:
            manifest=target/'dataset.json';manifest.write_text(canonical(c['manifest'])+'\n')
            built=build(target/'catalog.sqlite',manifest)
            cat=Catalog(target/'catalog.sqlite');cat.verify();cat.close()
            receipt={'candidate_hash':h,'manifest_hash':built['sha256'],'reviewer':approval[0],'approval_evidence':approval[1],'approved_at':approval[2]}
            target.joinpath('receipt.json').write_text(canonical(receipt)+'\n')
            # READY is the visibility marker, written after all files are flushed.
            import os
            for path in target.iterdir():
                with path.open('rb') as f:os.fsync(f.fileno())
                path.chmod(0o444)
            marker=target/'READY';marker.write_text(built['sha256']+'\n')
            with marker.open('rb') as f:os.fsync(f.fileno())
            marker.chmod(0o444)
            fd=os.open(target,os.O_RDONLY);os.fsync(fd);os.close(fd)
            fd=os.open(root,os.O_RDONLY);os.fsync(fd);os.close(fd)
            self.db.execute('INSERT INTO publications VALUES (?,?,?,?,?)',(c['version'],h,approval[0],str(target),time.time()))
            return receipt
        except BaseException:
            # Leave interrupted package for inspection; absent READY means unavailable.
            raise
