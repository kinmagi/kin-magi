"""Explicit acquisition, review, candidate, approval and publication commands."""
import argparse,json
from pathlib import Path
from pipeline import Stage
from scheduler import Scheduler

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',required=True);p.add_argument('--baseline');s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('acquire');a.add_argument('source',choices=['nist','pubchem','materials_project']);a.add_argument('--query',default='{}');a.add_argument('--refresh',action='store_true')
    s.add_parser('review')
    a=s.add_parser('candidate');a.add_argument('--ids',required=True);a.add_argument('--version',required=True);a.add_argument('--resolutions',default='{}')
    a=s.add_parser('approve');a.add_argument('hash');a.add_argument('--reviewer',required=True);a.add_argument('--evidence-file',required=True);a.add_argument('--licenses-reviewed',action='store_true')
    a=s.add_parser('publish');a.add_argument('hash');a.add_argument('--releases',required=True)
    a=s.add_parser('schedule');a.add_argument('--name',required=True);a.add_argument('--source',required=True);a.add_argument('--query',default='{}');a.add_argument('--interval',type=float,default=86400)
    s.add_parser('tick');args=p.parse_args();stage=Stage(args.stage,args.baseline)
    try:
        if args.command=='acquire':result=stage.acquire(args.source,json.loads(args.query),args.refresh)
        elif args.command=='review':result=stage.review()
        elif args.command=='candidate':result=stage.candidate([int(x) for x in args.ids.split(',')],args.version,json.loads(args.resolutions))
        elif args.command=='approve':stage.approve(args.hash,args.reviewer,Path(args.evidence_file).read_text(),licenses_reviewed=args.licenses_reviewed);result={'approved':args.hash}
        elif args.command=='publish':result=stage.publish(args.hash,args.releases)
        elif args.command=='schedule':Scheduler(stage).add(args.name,args.source,json.loads(args.query),args.interval);result={'scheduled':args.name}
        else:result=Scheduler(stage).tick()
        print(json.dumps(result,indent=2))
    finally:stage.close()
if __name__=='__main__':main()
