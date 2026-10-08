"""Offline integration demonstration. Existing databases are never overwritten."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment010'))
from engine import World
from reference import Catalog, build, UnsupportedProperty
from laboratory import Laboratory


def run(directory):
    out=Path(directory);out.mkdir(parents=True,exist_ok=True)
    paths=[out/name for name in ['reference.sqlite','world.sqlite','lab.sqlite','results.json']]
    if any(p.exists() for p in paths):raise FileExistsError('use a fresh output directory')
    version=build(paths[0])['version'];c=Catalog(paths[0]);w=World(paths[1]);w.explore(0)
    p=w.propose('erosion',[0]);w.submit('erosion','human',p);assert w.commit('erosion')['accepted']
    engine_state=w.state();engine_events=w.events();lab=Laboratory(paths[2],w,c)
    lab.create_object('sample',0,'al6061-t6',version,(1000,'g'))
    lab.create_object('receiver',0,'al6061-t6',version,(0,'kg'))
    capacity=lab.property('sample','specific_heat',temperature=(100,'K'))
    conductivity=lab.property('sample','thermal_conductivity',temperature=(100,'K'))
    rejected=lab.commit_transfer(lab.propose_transfer('sample','receiver',(2,'kg')))
    assert lab.commit_transfer(lab.propose_transfer('sample','receiver',(100,'g')))['accepted']
    try:lab.property('sample','electrical_resistivity')
    except UnsupportedProperty:missing_rejected=True
    else:missing_rejected=False
    before=lab.state();audit=lab.verify();lab.close();w.close();c.close()
    c=Catalog(paths[0]);w=World(paths[1]);lab=Laboratory(paths[2],w,c)
    checks={'unknown_rejected':missing_rejected,'excess_transfer_rejected':not rejected['accepted'],
            'restart_objects':before==lab.state(),'engine_state_isolated':engine_state==w.state(),
            'engine_events_preserved':engine_events==w.events(),
            'reference_read_only':c.verify(),'mass_conserved':sum(float(s['mass_kg']) for s in before.values())==1}
    result={'dataset_version':version,'dataset_sha256':c.dataset_hash(version),'checks':checks,
            'objects':lab.state(),'specific_heat_at_100K':capacity,'conductivity_at_100K':conductivity,
            'lab_audit':audit,'world_audit':w.verify()}
    lab.close();w.close();c.close();assert all(checks.values())
    paths[3].write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args()
    print(json.dumps(run(a.out)['checks'],indent=2))
