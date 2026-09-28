#!/usr/bin/env python3
import argparse, os, sys, time
from pymongo import MongoClient, ReturnDocument

def db(uri,name):
    c=MongoClient(uri,serverSelectionTimeoutMS=10000,retryWrites=True)
    c.admin.command("ping")
    return c,c[name]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("command",choices=["acquire","heartbeat","release","active"])
    p.add_argument("--uri",required=True); p.add_argument("--db",default="own_vps")
    p.add_argument("--runner-id",default=os.getenv("GITHUB_RUN_ID","unknown"))
    p.add_argument("--generation",default=os.getenv("GITHUB_RUN_NUMBER","0"))
    p.add_argument("--role",default="worker"); p.add_argument("--status",default="ready")
    p.add_argument("--lease",type=int,default=90); p.add_argument("--interval",type=int,default=20)
    a=p.parse_args()
    c,d=db(a.uri,a.db); now=time.time()
    try:
        if a.command=="acquire":
            doc=d.vps_leader.find_one_and_update(
                {"_id":"current","$or":[{"lease_until":{"$lt":now}},{"runner_id":str(a.runner_id)}]},
                {"$set":{"runner_id":str(a.runner_id),"generation":str(a.generation),
                         "lease_until":now+a.lease,"updated_at":now}},
                upsert=True,return_document=ReturnDocument.AFTER)
            if not doc or str(doc["runner_id"])!=str(a.runner_id):
                raise SystemExit("LEADER_LOCK_NOT_ACQUIRED")
            print("LEADER_LOCK_ACQUIRED"); return 0
        if a.command=="heartbeat":
            d.vps_runners.update_one({"_id":str(a.runner_id)},{"$set":{
                "runner_id":str(a.runner_id),"generation":str(a.generation),
                "role":a.role,"status":a.status,"heartbeat":time.time()}},upsert=True)
            if a.role=="active":
                d.vps_leader.update_one({"_id":"current","runner_id":str(a.runner_id)},
                    {"$set":{"generation":str(a.generation),"lease_until":time.time()+a.lease,
                             "updated_at":time.time()}},upsert=False)
            print("HEARTBEAT_OK"); return 0
        if a.command=="release":
            d.vps_leader.delete_one({"_id":"current","runner_id":str(a.runner_id)})
            print("LEADER_RELEASED"); return 0
        doc=d.vps_meta.find_one({"_id":"live"}) or {}
        print(doc.get("active_runner","")); return 0
    finally: c.close()

if __name__=="__main__": raise SystemExit(main())
