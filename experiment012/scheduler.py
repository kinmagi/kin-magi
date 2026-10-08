"""Durable due jobs. Invoke tick from cron/systemd; no unattended publication."""
import json,time
from compat import canonical
from connectors import CONNECTORS
class Scheduler:
    def __init__(self,stage,clock=time.time):self.stage=stage;self.clock=clock
    def add(self,name,source,query,interval_seconds):
        if not name or source not in CONNECTORS or not 60<=interval_seconds<=31536000:raise ValueError('job/source/interval invalid')
        # Queries persist in SQLite: credentials may ONLY come from environment.
        allowed={'nist':set(),'pubchem':{'cid'},'materials_project':{'material_id','terms_accepted'}}[source]
        if set(query)-allowed:raise ValueError('unknown or credential-bearing scheduler query')
        self.stage.db.execute('INSERT INTO jobs(name,source,query,interval_seconds,next_due) VALUES (?,?,?,?,?)',(name,source,canonical(query),interval_seconds,self.clock()))
    def tick(self,acquire=None,limit=10):
        if type(limit)!=int or not 1<=limit<=100:raise ValueError('bounded job limit required')
        acquire=acquire or self.stage.acquire;results=[]
        for _ in range(limit):
            db=self.stage.db;now=self.clock();db.execute('BEGIN IMMEDIATE')
            try:
                row=db.execute('SELECT name,source,query,interval_seconds FROM jobs WHERE next_due<=? AND lease_until<=? ORDER BY next_due,name LIMIT 1',(now,now)).fetchone()
                if not row:db.commit();break
                db.execute('UPDATE jobs SET lease_until=? WHERE name=?',(now+300,row[0]));db.commit()
            except BaseException:db.rollback();raise
            name,source,query,interval=row
            try:
                ids=acquire(source,json.loads(query),refresh=True);outcome='success';delay=interval
            except Exception as exc:
                # No exception text or credential-bearing requests persisted.
                ids=[];outcome='failed:'+type(exc).__name__;delay=min(interval,300)
            db.execute('UPDATE jobs SET next_due=?,lease_until=0,last_result=? WHERE name=?',(self.clock()+delay,outcome,name))
            results.append({'job':name,'result':outcome,'record_ids':ids})
        return results
