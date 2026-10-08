"""Source-backed coverage update: candidate only; no publication approval implied."""
import argparse,hashlib,json,sys
from pathlib import Path
from compat import ROOT,build,Catalog,digest
from connectors import NIST
from pipeline import Stage
sys.path.insert(0,str(ROOT.parent/'experiment010'))
from engine import World
from laboratory import Laboratory

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(out):
    out=Path(out);out.mkdir()  # Exclusive output; no generated file can be overwritten.
    old=out/'previous.sqlite';release=build(old);catalog=Catalog(old)
    world=World(out/'world.sqlite');world.explore(0)
    lab=Laboratory(out/'lab.sqlite',world,catalog)
    obj=lab.create_object('copper-sample',0,'copper',release['version'],('1','kg'))
    lab.close();world.close();catalog.close()
    protected={p.name:sha(p) for p in [old,out/'world.sqlite',out/'lab.sqlite']}
    stage=Stage(out/'staging.sqlite')
    evidence=json.loads(ROOT.joinpath('fixtures/nist_excerpt_metadata.json').read_text())
    body=ROOT.joinpath('fixtures/nist_excerpt.txt').read_bytes()
    assert hashlib.sha256(body).hexdigest()==evidence['sha256']
    stage.capture(body,evidence)
    ids=stage.ingest(NIST().parse(body,evidence))
    review=stage.review();new_ids=[r['id'] for r in review['records'] if r['classification']=='new']
    candidate=stage.candidate(new_ids,'cw012-demo-coverage.1')
    out.joinpath('candidate.json').write_text(json.dumps(candidate,indent=2)+'\n')
    out.joinpath('review.json').write_text(json.dumps(review,indent=2)+'\n')
    blocked=False
    try:stage.publish(candidate['hash'],out/'releases')
    except ValueError:blocked=True
    stage.close()
    stage=Stage(out/'staging.sqlite');recovered=stage.load_candidate(candidate['hash']);stage.close()
    catalogue=Catalog(old);world=World(out/'world.sqlite');lab=Laboratory(out/'lab.sqlite',world,catalogue)
    same_object=lab.state()['copper-sample']==obj
    world.verify();lab.verify();lab.close();world.close();catalogue.close()
    checks={'update_detected':len(new_ids)==1,'duplicate_detected':review['counts']['duplicate']==1,
        'candidate_validated':recovered['manifest']['version']==candidate['version'],
        'publication_without_approval_rejected':blocked,'old_release_unchanged':sha(old)==protected[old.name],
        'world_unchanged':sha(out/'world.sqlite')==protected['world.sqlite'],
        'laboratory_unchanged':sha(out/'lab.sqlite')==protected['lab.sqlite'],'object_restart_recovered':same_object}
    report={'checks':checks,'all_passed':all(checks.values()),'baseline_manifest_hash':release['sha256'],'candidate_hash':candidate['hash'],
        'update':'Add CODATA 2022 electron mass to local coverage; no claim of a historical CODATA revision.',
        'capture':'Source-backed, manually transcribed browser excerpt. Direct live HTTP blocked in this environment.',
        'published':False,'review':review}
    out.joinpath('demo_results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);args=p.parse_args();run(args.out)
