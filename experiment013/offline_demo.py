"""Finite offline source-excerpt replay plus explicitly synthetic change scenarios."""
import copy,hashlib,json,sys
from pathlib import Path
from legacy import ROOT,build,Catalog,canonical,NIST_URL
from verification import VerificationStage
from verified_transport import VerifiedTransport
from verified_scheduler import VerificationScheduler

class FixtureResponse:
    status=200
    def __init__(self,body,headers=None):self.body=body;self.headers=headers or {'Date':'Thu, 08 Oct 2026 00:00:00 GMT','Content-Type':'text/plain'}
    def read(self,limit):return self.body[:limit]
    def __enter__(self):return self
    def __exit__(self,*args):pass

def fixture_transport(stage,body,clock):
    return VerifiedTransport(stage,opener=lambda *a,**k:FixtureResponse(body),clock=clock,sleep=lambda d:None,mode='synthetic_fixture')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(out):
    out=Path(out);out.mkdir();old=out/'old.sqlite';release=build(old)
    sys.path.append(str(ROOT.parent/'experiment010'));from engine import World
    from laboratory import Laboratory
    cat=Catalog(old);world=World(out/'world.sqlite');world.explore(0);lab=Laboratory(out/'lab.sqlite',world,cat)
    object=lab.create_object('sample',0,'copper',release['version'],('1','kg'));lab.close();world.close();cat.close()
    protected={p.name:sha(p) for p in [old,out/'world.sqlite',out/'lab.sqlite']}
    now=[2000000000.];stage=VerificationStage(out/'staging.sqlite',clock=lambda:now[0])
    body=(ROOT.parent/'experiment012/fixtures/nist_excerpt.txt').read_bytes()
    # All response replays (even source-backed excerpts) are labelled synthetic transport.
    for i in range(2):
        now[0]+=10;stage.acquire('nist',transport=fixture_transport(stage,body,lambda:now[0]))
    # Engineered protocol variations ONLY. No invented values enter any catalogue.
    corrected=body.replace(b'2022 CODATA',b'2024 CODATA').replace(b'9.109 383 7139 e-31',b'9.109 383 7138 e-31')
    conflicting=corrected.replace(b'9.109 383 7138 e-31',b'9.109 383 7137 e-31')
    for b in [corrected,conflicting,corrected]:
        now[0]+=10;stage.acquire('nist',transport=fixture_transport(stage,b,lambda:now[0]))
    scheduler=VerificationScheduler(stage,clock=lambda:now[0]);scheduler.add('demo-job','nist',{},60)
    result=scheduler.tick(acquire=lambda source,query,refresh:stage.acquire(source,query,refresh,fixture_transport(stage,corrected,lambda:now[0])),limit=1)
    claimed=scheduler.claim()  # not due yet
    stage.verify();before=stage.monitoring();stage.close()
    stage=VerificationStage(out/'staging.sqlite',clock=lambda:now[0]);stage.verify();after=stage.monitoring();stage.close()
    cat=Catalog(old);world=World(out/'world.sqlite');lab=Laboratory(out/'lab.sqlite',world,cat);same_object=lab.state()['sample']==object;lab.verify();world.verify();lab.close();world.close();cat.close()
    checks={'new_detected':after['counts']['new']>0,'unchanged_detected':after['counts']['unchanged']>0,'synthetic_correction_detected':after['counts']['correction']>0,'synthetic_conflict_detected':after['counts']['conflict']>0,
        'reversion_not_mislabelled_unchanged':any(x['classification']=='conflict' and x['run']==5 for x in after['observations']),
        'scheduled_tick_succeeded':result[0]['status']=='success','staging_restart_equal':before==after,
        'catalogue_world_lab_unchanged':all(sha(out/name)==h for name,h in protected.items()),'object_dataset_pin_recovered':same_object,
        'nothing_approved_or_published':after['approved_count']==after['published_count']==0,'no_live_success_claimed':all(s['http_success_exchanges']==0 for s in after['sources'].values())}
    report={'mode':'offline replay; simulated corrections/conflicts are not scientific claims','checks':checks,'all_passed':all(checks.values()),'monitoring':after,'published':False}
    out.joinpath('offline_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'all_passed':report['all_passed'],'checks':checks},indent=2));return report
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();run(a.out)
