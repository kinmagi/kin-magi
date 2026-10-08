"""Opt-in finite live acquisition: two rounds; never a daemon or publication task."""
import argparse,json,os
from pathlib import Path
from verification import VerificationStage

def run(out,*,allow_live=False,rounds=2,include_mp=False):
    if allow_live is not True:raise ValueError('explicit allow_live required')
    if type(rounds)!=int or not 1<=rounds<=3:raise ValueError('one to three finite rounds required')
    out=Path(out);out.mkdir();stage=VerificationStage(out/'staging.sqlite');results=[]
    sources=[('nist',{}),('pubchem',{'cid':962})]
    if include_mp:sources.append(('materials_project',{'material_id':'mp-149','terms_accepted':os.getenv('CW_MP_TERMS_ACCEPTED')=='yes'}))
    try:
        for round in range(rounds):
            for source,query in sources:
                try:ids=stage.acquire(source,query,refresh=True);status='success'
                except Exception:ids=[];status='failed'  # Sanitized detailed outcomes remain in monitoring.
                results.append({'round':round+1,'source':source,'status':status,'record_ids':ids})
        stage.verify();monitor=stage.monitoring()
        verified_repeated=all(monitor['sources'][source]['outcomes']['success']==rounds and monitor['sources'][source]['http_success_exchanges']>=rounds for source,_ in sources)
        report={'mode':'real HTTP; forced refresh; finite opt-in run','rounds':rounds,'results':results,'verified_repeated_live_acquisition':verified_repeated,
            'monitoring':monitor,'published':False,'mp_requested':include_mp,'mp_credentials_present':bool(os.getenv('MP_API_KEY'))}
        out.joinpath('live_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'verified_repeated_live_acquisition':verified_repeated,'results':results},indent=2));return report
    finally:stage.close()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--allow-live',action='store_true');p.add_argument('--rounds',type=int,default=2);p.add_argument('--include-mp',action='store_true');a=p.parse_args();run(a.out,allow_live=a.allow_live,rounds=a.rounds,include_mp=a.include_mp)
