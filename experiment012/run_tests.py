"""Run 010–012 independently; protect and verify unchanged tracked baseline blobs."""
import hashlib,json,re,subprocess,sys,time
from pathlib import Path
from compat import ROOT

def run(out):
    out=Path(out)
    if out.exists():raise FileExistsError('fresh results path required')
    expected=json.loads(ROOT.joinpath('baseline_blobs.json').read_text());checks={}
    for path,sha in expected.items():
        body=(ROOT.parent/path).read_bytes();actual=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest();checks[path]=actual==sha
    suites=[]
    for name in ['experiment010','experiment011','experiment012']:
        p=subprocess.run([sys.executable,'-m','unittest','-v'],cwd=ROOT.parent/name,capture_output=True,text=True)
        log=p.stdout+p.stderr;n=re.search(r'Ran (\d+) tests?',log)
        suites.append({'suite':name,'count':int(n[1]) if n else None,'returncode':p.returncode,'output':log})
    report={'utc':time.time(),'python':sys.version.split()[0],'baseline_blobs_unchanged':checks,
        'all_passed':all(checks.values()) and all(x['returncode']==0 for x in suites),'suites':suites}
    out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'all_passed':report['all_passed'],'suites':[(s['suite'],s['count'],s['returncode']) for s in suites]},indent=2));return 0 if report['all_passed'] else 1
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();raise SystemExit(run(a.out))
