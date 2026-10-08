"""Persistent objects as a sidecar to unmodified Experiment 010.
No scientific catalog rows or Experiment 010 region/event rows are written here.
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime,timezone
from reference import ReferenceProvider, UnsupportedProperty, canonical, digest, require
from units import convert, number

def mass_value(value):
    x=number(value)
    require(0<=x<=number('1e12'),'mass outside supported ledger range 0–1e12 kg')
    require(x==x.quantize(number('1e-9')),'mass precision finer than 1e-9 kg unsupported')
    return x

class Laboratory:
    def __init__(self,path,world,catalog: ReferenceProvider):
        self.world=world;self.catalog=catalog;self.path=Path(path).resolve()
        require(self.path!=Path(world.db.execute('PRAGMA database_list').fetchone()[2]).resolve(),'laboratory and world must use separate databases')
        if hasattr(catalog,'path'):require(self.path!=catalog.path,'laboratory and reference must use separate databases')
        origin=world.db.execute('SELECT hash FROM events ORDER BY seq LIMIT 1').fetchone()
        require(origin is not None,'explore an engine region before opening a laboratory')
        self.world_anchor=origin[0]
        self.db=sqlite3.connect(self.path,timeout=10,isolation_level=None)
        self.db.execute('PRAGMA synchronous=FULL');self.db.execute('PRAGMA journal_mode=DELETE')
        tables={r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and 'lab_meta' not in tables:self.db.close();raise ValueError('refusing non-laboratory database')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS lab_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS objects(id TEXT PRIMARY KEY,record TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS lab_events(seq INTEGER PRIMARY KEY,record TEXT NOT NULL,previous_hash TEXT NOT NULL,hash TEXT NOT NULL);
          CREATE TRIGGER IF NOT EXISTS lab_event_update BEFORE UPDATE ON lab_events BEGIN SELECT RAISE(ABORT,'immutable lab events'); END;
          CREATE TRIGGER IF NOT EXISTS lab_event_delete BEFORE DELETE ON lab_events BEGIN SELECT RAISE(ABORT,'immutable lab events'); END;
        ''')
        self.db.execute("INSERT OR IGNORE INTO lab_meta VALUES ('schema','011.1')")
        self.db.execute('INSERT OR IGNORE INTO lab_meta VALUES (?,?)',('world_anchor',self.world_anchor))
        try:
            require(self.db.execute("SELECT value FROM lab_meta WHERE key='schema'").fetchone()[0]=='011.1','unsupported lab schema')
            self.verify()
        except BaseException:self.db.close();raise
    def close(self):self.db.close()
    def state(self):return {k:json.loads(v) for k,v in self.db.execute('SELECT * FROM objects ORDER BY id')}
    def events(self):return [json.loads(r[0]) for r in self.db.execute('SELECT record FROM lab_events ORDER BY seq')]
    def _validate_object(self,s):
        require(set(s)=={'id','region','material_id','dataset_version','dataset_sha256','mass_kg','version'},'invalid object schema')
        require(isinstance(s['id'],str) and bool(s['id']) and isinstance(s['region'],str),'invalid object identity')
        require(type(s['version']) is int and s['version']>=0 and mass_value(s['mass_kg'])>=0,'invalid object version/mass')
        require(s['region'] in self.world.state(),'object region unavailable in engine')
        self.catalog.material(s['material_id'],s['dataset_version'])
        require(self.catalog.dataset_hash(s['dataset_version'])==s['dataset_sha256'],'pinned scientific release content mismatch')
    def _event(self,kind,before,after,actor):
        require(isinstance(actor,str) and bool(actor),'actor required')
        row=self.db.execute('SELECT hash FROM lab_events ORDER BY seq DESC LIMIT 1').fetchone();prev=row[0] if row else '0'*64
        r={'kind':kind,'before':before,'after':after,'actor':actor,'utc':datetime.now(timezone.utc).isoformat(),'schema':'011.1'}
        self.db.execute('INSERT INTO lab_events(record,previous_hash,hash) VALUES (?,?,?)',(canonical(r),prev,digest({'previous':prev,'record':r})))
    def create_object(self,id,region,material_id,dataset_version,mass,actor='human'):
        """Explicit inventory introduction, not a physical mass-creation model."""
        kg=mass_value(convert(mass[0],mass[1],'kg'))
        s={'id':id,'region':str(region),'material_id':material_id,'dataset_version':dataset_version,
           'dataset_sha256':self.catalog.dataset_hash(dataset_version),'mass_kg':str(kg),'version':0}
        self._validate_object(s)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('INSERT INTO objects VALUES (?,?)',(id,canonical(s)))
            self._event('inventory_introduction',{}, {id:s},actor);self.db.commit();return s
        except BaseException:self.db.rollback();raise
    def property(self,id,name,**conditions):
        s=self.state().get(id)
        if s is None:raise UnsupportedProperty('unknown world object')
        self._validate_object(s)
        return self.catalog.property(s['material_id'],name,s['dataset_version'],**conditions)
    def propose_transfer(self,source,target,mass):
        states=self.state()
        if source==target or source not in states or target not in states:raise ValueError('two distinct objects required')
        return {'source':source,'target':target,'mass_kg':str(convert(mass[0],mass[1],'kg')),
                'versions':{i:states[i]['version'] for i in (source,target)}}
    def _transfer_after(self,proposal,before):
        require(isinstance(proposal,dict) and set(proposal)=={'source','target','mass_kg','versions'},'unsupported laboratory proposal')
        source,target=proposal['source'],proposal['target']
        require(source!=target and set(before)=={source,target},'two distinct objects required')
        require(set(proposal['versions'])==set(before),'missing versions')
        for id,s in before.items():
            self._validate_object(s)
            require(type(proposal['versions'][id]) is int and proposal['versions'][id]==s['version'],'stale laboratory proposal')
        a,b=before[source],before[target]
        require(all(a[k]==b[k] for k in ('material_id','dataset_version','dataset_sha256')),'different material identities/releases cannot mix')
        amount=mass_value(proposal['mass_kg']);require(0<amount<=number(a['mass_kg']),'invalid or excessive mass transfer')
        after={i:dict(s) for i,s in before.items()}
        after[source]['mass_kg']=str(number(a['mass_kg'])-amount)
        after[target]['mass_kg']=str(number(b['mass_kg'])+amount)
        for s in after.values():s['version']+=1;mass_value(s['mass_kg'])
        require(sum(number(s['mass_kg']) for s in before.values())==sum(number(s['mass_kg']) for s in after.values()),'mass conservation violation')
        return after
    def commit_transfer(self,proposal,actor='human'):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            try:
                require(isinstance(proposal,dict),'unsupported laboratory proposal')
                all_states=self.state();before={i:all_states[i] for i in (proposal['source'],proposal['target'])}
                after=self._transfer_after(proposal,before)
            except (ValueError,KeyError,TypeError) as exc:
                self.db.rollback();return {'accepted':False,'reasons':[str(exc)]}
            for i,s in after.items():self.db.execute('UPDATE objects SET record=? WHERE id=?',(canonical(s),i))
            self._event('mass_transfer',before,after,actor);self.db.commit();return {'accepted':True,'reasons':[]}
        except BaseException:self.db.rollback();raise
    def verify(self):
        require(self.db.execute("SELECT value FROM lab_meta WHERE key='world_anchor'").fetchone()[0]==self.world_anchor,'laboratory belongs to another engine world')
        require(self.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','laboratory corruption')
        replay={};prev='0'*64;seq=0
        for n,raw,previous,h in self.db.execute('SELECT * FROM lab_events ORDER BY seq'):
            r=json.loads(raw);require(n==seq+1 and previous==prev and h==digest({'previous':prev,'record':r}),'laboratory event chain mismatch')
            require(r['schema']=='011.1','laboratory event schema mismatch')
            before,after=r['before'],r['after']
            for i,s in after.items():self._validate_object(s);require(i==s['id'],'object identity mismatch')
            if r['kind']=='inventory_introduction':
                require(not before and len(after)==1 and all(i not in replay and s['version']==0 for i,s in after.items()),'invalid introduction event')
            elif r['kind']=='mass_transfer':
                require(len(before)==2 and set(after)==set(before) and all(replay.get(i)==s for i,s in before.items()),'invalid transfer precondition')
                losses=[i for i in before if number(before[i]['mass_kg'])>number(after[i]['mass_kg'])]
                require(len(losses)==1,'invalid mass transfer history');source=losses[0];target=next(i for i in before if i!=source)
                p={'source':source,'target':target,'mass_kg':str(number(before[source]['mass_kg'])-number(after[source]['mass_kg'])),
                   'versions':{i:s['version'] for i,s in before.items()}}
                require(self._transfer_after(p,before)==after,'invalid conserved transfer history')
            else:raise ValueError('unregistered laboratory event')
            replay.update(after);prev=h;seq=n
        require(replay==self.state(),'laboratory state differs from audited history')
        return {'verified':True,'objects':len(replay),'events':seq}
