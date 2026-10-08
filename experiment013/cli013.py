"""Staging/review CLI; no approval, release publishing or service installation command."""
import argparse,json
from verification import VerificationStage
from verified_scheduler import VerificationScheduler

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',required=True);s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('acquire');a.add_argument('source',choices=['nist','pubchem','materials_project']);a.add_argument('--query',default='{}')
    s.add_parser('monitor');s.add_parser('verify');s.add_parser('recover')
    a=s.add_parser('schedule');a.add_argument('--name',required=True);a.add_argument('--source',required=True);a.add_argument('--query',default='{}');a.add_argument('--interval',type=float,default=86400)
    a=s.add_parser('tick');a.add_argument('--allow-live',action='store_true');a.add_argument('--limit',type=int,default=3)
    args=p.parse_args()
    if args.command=='tick' and not args.allow_live:p.error('tick requires --allow-live; no unattended acquisition starts implicitly')
    stage=VerificationStage(args.stage)
    try:
        if args.command=='acquire':result=stage.acquire(args.source,json.loads(args.query),refresh=True)
        elif args.command=='monitor':result=stage.monitoring()
        elif args.command=='verify':result={'verified':stage.verify()}
        elif args.command=='recover':result={'recovered':stage.recover_interrupted()}
        elif args.command=='schedule':VerificationScheduler(stage).add(args.name,args.source,json.loads(args.query),args.interval);result={'scheduled':args.name,'started':False}
        else:result=VerificationScheduler(stage).tick(limit=args.limit)
        print(json.dumps(result,indent=2))
    finally:stage.close()
if __name__=='__main__':main()
