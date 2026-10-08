"""Bounded official-host GET transport. No redirects, scraping, or stored credentials."""
import hashlib,json,time,urllib.request,urllib.error
from email.utils import parsedate_to_datetime
from compat import canonical

class AccessUnavailable(RuntimeError):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise AccessUnavailable('redirect denied; review connector endpoint')

class Transport:
    def __init__(self,stage,opener=None,clock=time.time,sleep=time.sleep):
        self.stage=stage;self.clock=clock;self.sleep=sleep
        self.opener=opener or urllib.request.build_opener(NoRedirect()).open
    def get(self,source,url,headers=None,ttl=3600,refresh=False):
        from connectors import allowed_url, POLICIES
        if not allowed_url(source,url):raise AccessUnavailable('endpoint outside connector allowlist')
        if not 0<=ttl<=86400:raise ValueError('cache ttl outside supported range')
        key=hashlib.sha256(url.encode()).hexdigest()
        row=self.stage.db.execute('SELECT body,sha256,headers,fetched FROM responses WHERE key=?',(key,)).fetchone()
        if row and not refresh and self.clock()-row[3]<ttl:
            if hashlib.sha256(row[0]).hexdigest()!=row[1]:raise AccessUnavailable('corrupt cached response')
            return row[0],json.loads(row[2]),{'url':url,'retrieved_at':row[3],'sha256':row[1],'mode':'cache'}
        for attempt in range(3):
            # Reservation is durable and serializes clients sharing this staging file.
            self.stage.db.execute('BEGIN IMMEDIATE')
            try:
                prev=self.stage.db.execute('SELECT next_allowed FROM throttle WHERE source=?',(source,)).fetchone()
                start=max(self.clock(),prev[0] if prev else 0)
                self.stage.db.execute('INSERT OR REPLACE INTO throttle VALUES (?,?)',(source,start+POLICIES[source]['interval']))
                self.stage.db.commit()
            except BaseException:self.stage.db.rollback();raise
            delay=start-self.clock()
            if delay>60:raise AccessUnavailable('source cooling down; scheduled retry required')
            if delay>0:self.sleep(delay)
            retry_delay=min(2**attempt,30)
            try:
                request=urllib.request.Request(url,headers={'User-Agent':'CuriousWorlds-Experiment012/1.0',**(headers or {})})
                with self.opener(request,timeout=25) as response:
                    body=response.read(2_000_001)
                    if len(body)>2_000_000:raise AccessUnavailable('response exceeds size limit')
                    safe_headers={k.lower():v for k,v in response.headers.items() if k.lower() in {'etag','last-modified','content-type','x-throttling-control'}}
                sha=hashlib.sha256(body).hexdigest();now=self.clock()
                if any(color in safe_headers.get('x-throttling-control','').lower() for color in ('red','black')):
                    self.stage.db.execute('INSERT OR REPLACE INTO throttle VALUES (?,?)',(source,now+60))
                self.stage.db.execute('BEGIN IMMEDIATE')
                try:
                    self.stage.db.execute('INSERT OR REPLACE INTO responses VALUES (?,?,?,?,?,?)',(key,url,body,sha,canonical(safe_headers),now))
                    self.stage.db.execute('INSERT INTO attempts(source,utc,outcome) VALUES (?,?,?)',(source,now,'success'))
                    self.stage.db.commit()
                except BaseException:self.stage.db.rollback();raise
                return body,safe_headers,{'url':url,'retrieved_at':now,'sha256':sha,'mode':'live'}
            except urllib.error.HTTPError as exc:
                self.stage.db.execute('INSERT INTO attempts(source,utc,outcome) VALUES (?,?,?)',(source,self.clock(),'HTTP '+str(exc.code)))
                if exc.code not in {429,500,502,503,504}:raise AccessUnavailable('source HTTP '+str(exc.code)) from None
                value=exc.headers.get('Retry-After')
                if value:
                    try:retry_delay=max(retry_delay,float(value))
                    except ValueError:
                        try:retry_delay=max(retry_delay,parsedate_to_datetime(value).timestamp()-self.clock())
                        except (TypeError,ValueError):pass
            except (urllib.error.URLError,TimeoutError,OSError) as exc:
                self.stage.db.execute('INSERT INTO attempts(source,utc,outcome) VALUES (?,?,?)',(source,self.clock(),type(exc).__name__))
                # Never save exception strings: proxy URLs or headers could contain credentials.
                if attempt==2:raise AccessUnavailable('network unavailable after bounded retries') from None
            if retry_delay>60:
                self.stage.db.execute('INSERT OR REPLACE INTO throttle VALUES (?,?)',(source,self.clock()+retry_delay))
                raise AccessUnavailable('Retry-After requires later scheduled retry')
            if attempt<2:self.sleep(retry_delay)
        raise AccessUnavailable('source unavailable after bounded retries')
