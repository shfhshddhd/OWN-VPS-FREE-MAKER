#!/usr/bin/env python3
import argparse
import json
import os
import time
from pymongo import MongoClient, ReturnDocument

def open_db(uri, name):
    client = MongoClient(uri, serverSelectionTimeoutMS=10000, retryWrites=True)
    client.admin.command("ping")
    return client, client[name]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["acquire","heartbeat","release","active","status"])
    ap.add_argument("--uri", required=True)
    ap.add_argument("--db", default="own_vps")
    ap.add_argument("--runner-id", default=os.getenv("GITHUB_RUN_ID","unknown"))
    ap.add_argument("--generation", default=os.getenv("GITHUB_RUN_NUMBER","0"))
    ap.add_argument("--role", default="worker")
    ap.add_argument("--status", default="ready")
    ap.add_argument("--lease", type=int, default=90)
    ap.add_argument("--interval", type=int, default=20)
    a = ap.parse_args()
    client, db = open_db(a.uri, a.db)
    now = time.time()
    try:
        if a.command == "acquire":
            try:
                doc = db.vps_leader.find_one_and_update(
                    {"_id":"current",
                     "$or":[{"lease_until":{"$lt":now}},{"runner_id":str(a.runner_id)}]},
                    {"$set":{"runner_id":str(a.runner_id),
                             "generation":str(a.generation),
                             "lease_until":now+a.lease,
                             "updated_at":now}},
                    upsert=True,
                    return_document=ReturnDocument.AFTER,
                )
            except Exception:
                doc = None
            if not doc or str(doc.get("runner_id")) != str(a.runner_id):
                raise SystemExit("LEADER_LOCK_NOT_ACQUIRED")
            print("LEADER_LOCK_ACQUIRED")
            return 0

        if a.command == "heartbeat":
            ts = time.time()
            db.vps_runners.update_one(
                {"_id":str(a.runner_id)},
                {"$set":{"runner_id":str(a.runner_id),
                         "generation":str(a.generation),
                         "role":a.role,
                         "status":a.status,
                         "heartbeat":ts}},
                upsert=True,
            )
            if a.role == "active":
                leader = db.vps_leader.update_one(
                    {"_id":"current","runner_id":str(a.runner_id)},
                    {"$set":{"generation":str(a.generation),
                             "lease_until":ts+a.lease,
                             "updated_at":ts}},
                )
                if leader.matched_count != 1:
                    raise SystemExit("LEADER_LEASE_LOST")
            print("HEARTBEAT_OK")
            return 0

        if a.command == "release":
            db.vps_leader.delete_one({"_id":"current","runner_id":str(a.runner_id)})
            db.vps_runners.update_one(
                {"_id":str(a.runner_id)},
                {"$set":{"status":"retiring","retired_at":time.time()}},
            )
            print("LEADER_RELEASED")
            return 0

        if a.command == "active":
            doc = db.vps_meta.find_one({"_id":"live"}) or {}
            print(doc.get("active_runner",""))
            return 0

        live = db.vps_meta.find_one({"_id":"live"}) or {}
        runner_id = str(live.get("active_runner",""))
        runner = db.vps_runners.find_one({"_id":runner_id}) or {}
        leader = db.vps_leader.find_one({"_id":"current"}) or {}
        hb = runner.get("heartbeat")
        lease_until = leader.get("lease_until")
        lease_remaining = max(0.0, float(lease_until) - time.time()) if lease_until else 0.0
        leader_lease_active = bool(lease_until and float(lease_until) > time.time())

        print(json.dumps({
            "active_runner":runner_id,
            "generation":str(live.get("generation","")),
            "status":runner.get("status",""),
            "heartbeat":hb,
            "heartbeat_age":(time.time()-hb) if hb else None,
            "leader_runner":str(leader.get("runner_id","")),
            "leader_lease_until":lease_until,
            "leader_lease_active":leader_lease_active,
            "leader_lease_remaining":lease_remaining,
        }, separators=(",",":")))
        return 0
    finally:
        client.close()

if __name__ == "__main__":
    raise SystemExit(main())
