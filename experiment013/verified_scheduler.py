"""Explicit bounded ticks with durable leases and fenced stale completions."""
import json,time,uuid,math
from legacy import canonical
class VerificationScheduler:
    def __init__(self,stage,clock=time.time):self.stage=stage;self.clock=clock
    def add(self,name,source,query,interval=86400):
        self.stage.query(source,query)
        if not isinstance(name,str) or not name or not isinstance(interval,(int,float)) or isinstance(interval,bool) or not math.isfinite(interval) or not 60<=interval<=31536000:raise ValueError('invalid scheduled job')
        self.stage.db.execute('INSERT INTO verification_jobs(name,source,query,interval_seconds,next_due) VALUES (?,?,?,?,?)',(name,source,canonical(query),interval,self.clock()))
    def claim(self):
        db=self.stage.db;now=self.clock();db.execute('BEGIN IMMEDIATE')
        try:
            row=db.execute('SELECT name,source,query,interval_seconds FROM verification_jobs WHERE next_due<=? AND lease_until<=? ORDER BY next_due,name LIMIT 1',(now,now)).fetchone()
            if not row:db.commit();return None
            token=uuid.uuid4().hex;db.execute('UPDATE verification_jobs SET token=?,lease_until=? WHERE name=?',(token,now+300,row[0]));db.commit();return (*row,token)
        except BaseException:db.rollback();raise
    def finish(self,claim,outcome):
        name,source,query,interval,token=claim;delay=interval if outcome=='success' else min(interval,300)
        # A reclaimed job rejects completion from an expired worker.
        return self.stage.db.execute('UPDATE verification_jobs SET next_due=?,lease_until=0,token=NULL,last_result=? WHERE name=? AND token=? AND lease_until>?',(self.clock()+delay,outcome,name,token,self.clock())).rowcount==1
    def tick(self,acquire=None,limit=3):
        if type(limit)!=int or not 1<=limit<=10:raise ValueError('tick limit 1–10 required')
        self.stage.recover_interrupted();results=[];acquire=acquire or self.stage.acquire
        for _ in range(limit):
            claim=self.claim()
            if claim is None:break
            try:
                ids=acquire(claim[1],json.loads(claim[2]),refresh=True);outcome='success'
            except Exception as exc:ids=[];outcome='failed:'+type(exc).__name__
            results.append({'job':claim[0],'status':outcome,'record_ids':ids,'completion_committed':self.finish(claim,outcome)})
        return results
