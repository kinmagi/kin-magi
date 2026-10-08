"""Isolated regression suites plus verification of every historical tracked blob."""
import hashlib,json,re,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def run(out):
    out=Path(out)
    if out.exists():raise FileExistsError('fresh output path required')
    expected=json.loads(ROOT.joinpath('baseline_blobs.json').read_text());before={}
    for path,h in expected.items():
        body=ROOT.parent.joinpath(path).read_bytes();before[path]=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()==h
    suites=[]
    for name in ['experiment010','experiment011','experiment012','experiment013']:
        p=subprocess.run([sys.executable,'-m','unittest','-v'],cwd=ROOT.parent/name,capture_output=True,text=True);output=p.stdout+p.stderr;count=re.search(r'Ran (\d+) tests?',output)
        suites.append({'suite':name,'tests':int(count[1]) if count else None,'returncode':p.returncode,'output':output})
    after={}
    for path,h in expected.items():
        body=ROOT.parent.joinpath(path).read_bytes();after[path]=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()==h
    data={'utc':time.time(),'python':sys.version.split()[0],'all_passed':all(before.values()) and all(after.values()) and all(x['returncode']==0 for x in suites),'baseline_unchanged_before':before,'baseline_unchanged_after':after,'suites':suites}
    out.write_text(json.dumps(data,indent=2)+'\n');print(json.dumps({'all_passed':data['all_passed'],'suites':[(x['suite'],x['tests']) for x in suites]},indent=2));return 0 if data['all_passed'] else 1
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();raise SystemExit(run(a.out))
