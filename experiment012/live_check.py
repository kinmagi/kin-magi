"""Opt-in small real API checks. Blocked/missing access is reported, never called a pass."""
import argparse,json,os,tempfile,time
from pipeline import Stage
from compat import ROOT

def run(out):
    target=__import__('pathlib').Path(out)
    if target.exists():raise FileExistsError('fresh live results path required')
    results=[]
    with tempfile.TemporaryDirectory() as tmp:
        stage=Stage(__import__('pathlib').Path(tmp)/'stage.sqlite')
        for source,query in [('nist',{}),('pubchem',{'cid':962}),('materials_project',{'material_id':'mp-149','terms_accepted':os.getenv('CW_MP_TERMS_ACCEPTED')=='yes'})]:
            try:
                ids=stage.acquire(source,query,refresh=True)
                rows=[r for r in stage.review()['records'] if r['id'] in ids]
                ok=bool(ids) and all(r['accepted_format'] for r in rows)
                results.append({'source':source,'status':'passed' if ok else 'validation_failed','records':rows})
            except Exception as exc:
                # Sanitized access failures; detailed network policy reported separately.
                results.append({'source':source,'status':'unavailable','exception_type':type(exc).__name__,
                    'reason':str(exc) if type(exc).__name__ in {'AccessUnavailable','ValueError'} else 'source request failed'})
        stage.close()
    data={'utc':time.time(),'mode':'real official-endpoint acquisition; no simulated responses','results':results,
        'all_live_passed':all(r['status']=='passed' for r in results),'published':False}
    target.write_text(json.dumps(data,indent=2)+'\n');print(json.dumps(data,indent=2));return data
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();run(a.out)
