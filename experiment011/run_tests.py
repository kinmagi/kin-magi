"""Run both suites in their own import contexts and save inspectable results."""
import argparse
import json
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path

def run(out):
    root=Path(__file__).resolve().parent;reports=[]
    for name,directory in [('experiment010',root.parent/'experiment010'),('experiment011',root)]:
        p=subprocess.run([sys.executable,'-m','unittest','-v'],cwd=directory,capture_output=True,text=True)
        reports.append({'suite':name,'command':'python -m unittest -v','returncode':p.returncode,'output':p.stdout+p.stderr})
    data={'utc':datetime.now(timezone.utc).isoformat(),'python':sys.version.split()[0],
          'all_passed':all(r['returncode']==0 for r in reports),'suites':reports}
    target=Path(out)
    if target.exists():raise FileExistsError('use a fresh results path')
    target.write_text(json.dumps(data,indent=2)+'\n')
    for r in reports:print(r['output'])
    return 0 if data['all_passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();raise SystemExit(run(a.out))
