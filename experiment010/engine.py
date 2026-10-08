"""SQLite authority. Producers submit data; commit always revalidates under lock."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from models import MODEL_VERSION, MODELS, substrate, valid_state
from validation import validate

def encode(x): return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x): return hashlib.sha256(encode(x).encode()).hexdigest()

class World:
    def __init__(self,path):
        self.db=sqlite3.connect(path,timeout=10,isolation_level=None)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA journal_mode=DELETE')
        tables={r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and 'metadata' not in tables:
            self.db.close();raise ValueError('not an Experiment 010 database; refusing legacy database')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS regions(id TEXT PRIMARY KEY,data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY,actor TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,verdict TEXT);
        CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,record TEXT NOT NULL,previous_hash TEXT NOT NULL,hash TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS immutable_events_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'immutable events'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_events_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'immutable events'); END;
        ''')
        self.db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',('model_version',MODEL_VERSION))
        if self.db.execute('SELECT value FROM metadata WHERE key=?',('model_version',)).fetchone()[0]!=MODEL_VERSION:
            self.db.close();raise ValueError('model version mismatch; explicit migration required')
        try:self.verify()
        except Exception:self.db.close();raise

    def close(self): self.db.close()
    def state(self):return {k:json.loads(v) for k,v in self.db.execute('SELECT id,data FROM regions ORDER BY id')}
    def events(self):return [json.loads(r[0]) for r in self.db.execute('SELECT record FROM events ORDER BY seq')]
    def _event(self,kind,before,after,actor,proposal_id=None):
        row=self.db.execute('SELECT hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        previous=row[0] if row else '0'*64
        record={'kind':kind,'before':before,'after':after,'actor':actor,'proposal_id':proposal_id,
                'model_version':MODEL_VERSION,'utc':datetime.now(timezone.utc).isoformat()}
        self.db.execute('INSERT INTO events(record,previous_hash,hash) VALUES (?,?,?)',
                        (encode(record),previous,digest({'previous':previous,'record':record})))

    def explore(self,index):
        candidate=substrate(index);key=str(index)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT data FROM regions WHERE id=?',(key,)).fetchone()
            if row:self.db.commit();return json.loads(row[0]),False
            valid_state(candidate)
            for n,s in self.state().items():
                if int(n)==index-1 and s['right_boundary_mm']!=candidate['left_boundary_mm']:raise ValueError('left boundary mismatch')
                if int(n)==index+1 and candidate['right_boundary_mm']!=s['left_boundary_mm']:raise ValueError('right boundary mismatch')
            self.db.execute('INSERT INTO regions VALUES (?,?)',(key,encode(candidate)))
            self._event('generation',{}, {key:candidate},'substrate')
            self.db.commit();return candidate,True
        except BaseException:self.db.rollback();raise

    def propose(self,operation,targets):
        """Deterministic producer convenience; any future AI uses the same submission API."""
        states=self.state();before={str(i):states[str(i)] for i in targets}
        return {'operation':operation,'versions':{k:s['version'] for k,s in before.items()},
                'after':MODELS[operation].solve(before)}

    def submit(self,proposal_id,actor,payload):
        if not isinstance(proposal_id,str) or not proposal_id or not isinstance(actor,str) or not actor:raise ValueError('id and actor required')
        raw=encode(payload)
        self.db.execute('INSERT INTO proposals VALUES (?,?,?, ?,NULL)',(proposal_id,actor,raw,'pending'))

    def commit(self,proposal_id):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT actor,payload,status,verdict FROM proposals WHERE id=?',(proposal_id,)).fetchone()
            if row is None:raise KeyError(proposal_id)
            actor,raw,status,verdict=row
            if status!='pending':self.db.commit();return json.loads(verdict)
            payload=json.loads(raw);before={};canonical=None
            try:
                if not isinstance(payload,dict) or set(payload)!={'operation','versions','after'}:raise ValueError('invalid proposal envelope')
                versions=payload['versions'];states=self.state()
                if not isinstance(versions,dict) or not versions:raise ValueError('missing versions')
                for k,v in versions.items():
                    if k not in states or type(v) is not int or v!=states[k]['version']:raise ValueError('stale/missing region')
                    before[k]=states[k]
                verdict,canonical=validate(before,payload['operation'],payload['after'])
            except (ValueError,KeyError,TypeError) as e:verdict={'accepted':False,'reasons':[str(e)]}
            if verdict['accepted']:
                for k,s in canonical.items():self.db.execute('UPDATE regions SET data=? WHERE id=?',(encode(s),k))
                self._event(payload['operation'],before,canonical,actor,proposal_id)
            self.db.execute('UPDATE proposals SET status=?,verdict=? WHERE id=?',('committed' if verdict['accepted'] else 'rejected',encode(verdict),proposal_id))
            self.db.commit();return verdict
        except BaseException:self.db.rollback();raise

    def verify(self):
        """Replay immutable history and compare to authoritative materialized state."""
        if self.db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite corruption')
        replay={};previous='0'*64;seq=0
        for number,raw,prev,h in self.db.execute('SELECT * FROM events ORDER BY seq'):
            record=json.loads(raw)
            if number!=seq+1 or prev!=previous or h!=digest({'previous':prev,'record':record}):raise ValueError('event chain mismatch')
            if record['model_version']!=MODEL_VERSION:raise ValueError('event model mismatch')
            before,after=record['before'],record['after']
            if record['kind']=='generation':
                if before or len(after)!=1:raise ValueError('invalid generation history')
                for k,s in after.items():
                    if k in replay or s!=substrate(int(k)):raise ValueError('invalid substrate history')
            else:
                if any(replay.get(k)!=v for k,v in before.items()):raise ValueError('event precondition mismatch')
                verdict,expected=validate(before,record['kind'],after)
                if not verdict['accepted'] or expected!=after:raise ValueError('invalid physical event')
            replay.update(after);previous=h;seq=number
        if replay!=self.state():raise ValueError('state differs from audited history')
        return {'events':seq,'regions':len(replay),'verified':True}
