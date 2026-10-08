"""Instrumented bounded GETs on the existing official endpoint allowlist."""
import hashlib,json,math,time,urllib.request,urllib.error
from email.utils import parsedate_to_datetime
from legacy import canonical,digest,allowed_url,POLICIES,AccessUnavailable,NoRedirect

SAFE_HEADERS={'date','last-modified','etag','content-type','retry-after','x-throttling-control'}
class VerifiedTransport:
    def __init__(self,stage,opener=None,clock=time.time,sleep=time.sleep,timeout=15,max_attempts=3,total_seconds=120,mode='live'):
        if not 0<timeout<=25 or not 1<=max_attempts<=3 or not 0<total_seconds<=180 or mode not in {'live','synthetic_fixture'}:raise ValueError('invalid bounded transport configuration')
        self.stage=stage;self.clock=clock;self.sleep=sleep;self.timeout=timeout;self.max_attempts=max_attempts;self.total_seconds=total_seconds;self.mode=mode
        if opener is not None and mode!='synthetic_fixture':raise ValueError('injected transport must be labelled synthetic_fixture')
        self.opener=opener or urllib.request.build_opener(NoRedirect()).open
    def _exchange(self,source,url,status,body,headers,outcome):
        utc=self.clock();h=hashlib.sha256(body).hexdigest() if body is not None else None
        metadata={'run':self.stage.active_run,'source':source,'url':url,'utc':utc,'status':status,'sha256':h,'headers':headers,'outcome':outcome,'origin':self.mode}
        self.stage.db.execute('INSERT INTO exchanges(run_id,source,url,utc,status,body,sha256,headers,outcome,origin,evidence_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (self.stage.active_run,source,url,utc,status,body,h,canonical(headers),outcome,self.mode,digest(metadata)))

    def _cooldown(self,source,until):
        self.stage.db.execute('INSERT INTO throttle VALUES (?,?) ON CONFLICT(source) DO UPDATE SET next_allowed=MAX(next_allowed,excluded.next_allowed)',(source,until))
    def _wait(self,seconds,deadline):
        if seconds>60 or self.clock()+seconds>=deadline:raise AccessUnavailable('deferred: cooldown or request deadline')
        if seconds>0:self.sleep(seconds)
    def get(self,source,url,headers=None,ttl=3600,refresh=False):
        if not allowed_url(source,url):raise AccessUnavailable('endpoint denied by connector allowlist')
        if not 0<=ttl<=86400:raise ValueError('invalid cache TTL')
        cache_key=hashlib.sha256(url.encode()).hexdigest();db=self.stage.db
        row=db.execute('SELECT body,sha256,headers,fetched FROM responses WHERE key=?',(cache_key,)).fetchone()
        origin=db.execute('SELECT origin FROM cache_origin WHERE key=?',(cache_key,)).fetchone()
        if row and origin==(self.mode,) and not refresh and 0<=self.clock()-row[3]<ttl:
            if hashlib.sha256(row[0]).hexdigest()!=row[1]:raise AccessUnavailable('corrupt cache')
            h=json.loads(row[2]);self._exchange(source,url,None,row[0],h,'cache_hit')
            return row[0],h,{'url':url,'retrieved_at':row[3],'sha256':row[1],'mode':'cache' if self.mode=='live' else self.mode}
        deadline=self.clock()+self.total_seconds
        for attempt in range(self.max_attempts):
            db.execute('BEGIN IMMEDIATE')
            try:
                row=db.execute('SELECT next_allowed FROM throttle WHERE source=?',(source,)).fetchone();start=max(self.clock(),row[0] if row else 0)
                if start>=deadline:db.commit();raise AccessUnavailable('deferred: source cooldown')
                db.execute('INSERT OR REPLACE INTO throttle VALUES (?,?)',(source,start+POLICIES[source]['interval']));db.commit()
            except BaseException:
                if db.in_transaction:db.rollback()
                raise
            self._wait(start-self.clock(),deadline)
            delay=2**attempt
            try:
                request=urllib.request.Request(url,headers={'User-Agent':'CuriousWorlds-Experiment013/1.0',**(headers or {})})
                with self.opener(request,timeout=min(self.timeout,deadline-self.clock())) as response:
                    status=getattr(response,'status',200);h={k.lower():v for k,v in response.headers.items() if k.lower() in SAFE_HEADERS}
                    body=response.read(2_000_001)
                if len(body)>2_000_000:
                    self._exchange(source,url,status,None,h,'oversized_response');raise AccessUnavailable('response exceeds 2 MB evidence limit')
                if not 200<=status<300:
                    self._exchange(source,url,status,body,h,'unexpected_status');raise AccessUnavailable('unexpected HTTP status')
                sha=hashlib.sha256(body).hexdigest();now=self.clock()
                self._exchange(source,url,status,body,h,'http_success')
                db.execute('INSERT OR REPLACE INTO responses VALUES (?,?,?,?,?,?)',(cache_key,url,body,sha,canonical(h),now))
                db.execute('INSERT OR REPLACE INTO cache_origin VALUES (?,?)',(cache_key,self.mode))
                if any(c in h.get('x-throttling-control','').lower() for c in ('red','black')):self._cooldown(source,now+60)
                return body,h,{'url':url,'retrieved_at':now,'sha256':sha,'mode':self.mode}
            except urllib.error.HTTPError as exc:
                h={k.lower():v for k,v in (exc.headers or {}).items() if k.lower() in SAFE_HEADERS}
                # Exact error bytes where bounded; error text is never interpolated into reports.
                try:body=exc.read(2_000_001) if exc.fp else b''
                except (OSError,TimeoutError):body=b''
                finally:exc.close()
                self._exchange(source,url,exc.code,body if len(body)<=2_000_000 else None,h,'http_error')
                if exc.code not in {429,500,502,503,504}:raise AccessUnavailable('source HTTP '+str(exc.code)) from None
                retry=h.get('retry-after')
                if retry:
                    try:parsed=float(retry)
                    except ValueError:
                        try:parsed=parsedate_to_datetime(retry).timestamp()-self.clock()
                        except (ValueError,TypeError,OverflowError):parsed=0
                    if math.isfinite(parsed):delay=max(delay,parsed)
                self._cooldown(source,self.clock()+delay)
            except (urllib.error.URLError,TimeoutError,OSError) as exc:
                outcome='timeout' if isinstance(exc,TimeoutError) or isinstance(getattr(exc,'reason',None),TimeoutError) else 'network_error'
                # Distinguish destination denial from a retryable transient without persisting exception text.
                denied='403' in str(getattr(exc,'reason','')) and 'tunnel' in str(getattr(exc,'reason','')).lower()
                permission=isinstance(getattr(exc,'reason',None),PermissionError) or isinstance(exc,PermissionError)
                if permission:outcome='execution_permission_denied'
                elif denied:outcome='destination_policy_denied'
                self._exchange(source,url,None,None,{},outcome)
                if permission:raise AccessUnavailable('execution network permission denied') from None
                if denied:raise AccessUnavailable('destination policy denied; configure permitted host access') from None
            if attempt+1<self.max_attempts:self._wait(delay,deadline)
        raise AccessUnavailable('bounded attempts exhausted')
