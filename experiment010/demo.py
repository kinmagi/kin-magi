"""Offline demonstration. Refuses to overwrite an existing run."""
import argparse
import json
from pathlib import Path
from engine import World
from models import inventories

def run(path):
    if Path(path).exists():raise FileExistsError('use a fresh database path')
    w=World(path);w.explore(1);initial=w.state()
    bad=w.propose('erosion',[1]);bad['after']['1']['shore_tonnes']+=10
    w.submit('bad','ai-fixture',bad);rejected=w.commit('bad')
    unchanged=w.state()==initial
    for id,op,targets in [('water','equalization',[1]),('coast','erosion',[1])]:
        w.submit(id,'deterministic-tool',w.propose(op,targets));assert w.commit(id)['accepted']
    w.explore(2);before_transfer=inventories(w.state())
    w.submit('transfer','deterministic-tool',w.propose('boundary_transfer',[1,2]));assert w.commit('transfer')['accepted']
    after=w.state();audit=w.verify();events=w.events();w.close()
    w=World(path);returned,generated=w.explore(1)
    results={'scope':'offline; no autonomous agents or live AI; coastal models illustrative',
             'initial':initial,'final':after,'rejection':rejected,'audit':audit,'events':events,
             'checks':{'rejected_unchanged':unchanged,'restart_persisted':w.state()==after,
                       'not_regenerated':not generated,'cross_boundary_conserved':inventories(after)==before_transfer,
                       'boundary_continuity':after['1']['right_boundary_mm']==after['2']['left_boundary_mm']}}
    w.close();assert all(results['checks'].values());return results

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',default='world010.sqlite');p.add_argument('--out',default='results010.json');a=p.parse_args()
    if Path(a.out).exists():raise FileExistsError('use a fresh results path')
    result=run(a.db);Path(a.out).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['checks'],indent=2))
