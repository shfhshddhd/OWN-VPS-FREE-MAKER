#!/usr/bin/env python3
import argparse
import hashlib
import os
import stat
import subprocess
import time
from pathlib import Path

from pymongo import MongoClient
import gridfs

DEFAULT_PATHS = [
    "/opt/vps-data",
    "/root/.pm2",
    "/etc/ssh/sshd_config.d/99-own-vps.conf",
]

EXCLUDE_DIRS = {"/proc", "/sys", "/dev", "/run", "/tmp", "/var/lib/apt/lists"}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_files(roots):
    seen = set()
    for root in roots:
        p = Path(root)
        if not p.exists():
            continue
        if p.is_file():
            path = str(p.resolve())
            if path not in seen:
                seen.add(path)
                yield path
            continue
        for base, dirs, files in os.walk(p, followlinks=False):
            base_abs = os.path.abspath(base)
            dirs[:] = [
                d for d in dirs
                if os.path.abspath(os.path.join(base_abs, d)) not in EXCLUDE_DIRS
            ]
            for name in files:
                path = os.path.abspath(os.path.join(base_abs, name))
                try:
                    st = os.lstat(path)
                    if stat.S_ISREG(st.st_mode) and path not in seen:
                        seen.add(path)
                        yield path
                except OSError:
                    continue


def package_manifest():
    try:
        return subprocess.check_output(
            ["dpkg-query", "-W", "-f=${Package}\t${Version}\n"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return ""


def connect(uri, db_name):
    client = MongoClient(uri, serverSelectionTimeoutMS=10000, retryWrites=True)
    client.admin.command("ping")
    db = client[db_name]
    return client, db, gridfs.GridFS(db, collection="vps_files")


def event(db, event_type, runner_id, generation, **extra):
    doc = {
        "event": event_type,
        "runner_id": str(runner_id),
        "generation": str(generation),
        "created_at": time.time(),
    }
    doc.update(extra)
    db.vps_events.insert_one(doc)


def managed(path, roots):
    absolute = os.path.abspath(path)
    for root in roots:
        root_abs = os.path.abspath(root).rstrip("/")
        if absolute == root_abs or absolute.startswith(root_abs + "/"):
            return True
    return False


def upload_if_changed(fs, files, path, runner_id, generation):
    try:
        before = os.stat(path)
        digest = sha256_file(path)
        after = os.stat(path)
        if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
            return False

        old = files.find_one({"path": path, "deleted": False})
        if old and old.get("sha256") == digest:
            return True

        existing = fs.find_one({"sha256": digest})
        if existing is None:
            with open(path, "rb") as f:
                fid = fs.put(
                    f,
                    filename=os.path.basename(path),
                    sha256=digest,
                    source_path=path,
                    runner_id=str(runner_id),
                    generation=str(generation),
                )
        else:
            fid = existing._id

        files.update_one(
            {"path": path},
            {"$set": {
                "path": path,
                "sha256": digest,
                "size": after.st_size,
                "mtime_ns": after.st_mtime_ns,
                "mode": stat.S_IMODE(after.st_mode),
                "file_id": fid,
                "deleted": False,
                "runner_id": str(runner_id),
                "generation": str(generation),
                "updated_at": time.time(),
            }},
            upsert=True,
        )
        return True
    except (OSError, IOError):
        return False


def sync_once(db, fs, roots, runner_id, generation):
    files = db.vps_files
    current = set()
    uploaded = 0

    for path in safe_files(roots):
        current.add(path)
        if upload_if_changed(fs, files, path, runner_id, generation):
            uploaded += 1

    for doc in files.find({"deleted": False}, {"path": 1}):
        path = doc["path"]
        if managed(path, roots) and path not in current and not os.path.exists(path):
            files.update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "deleted": True,
                    "updated_at": time.time(),
                    "runner_id": str(runner_id),
                    "generation": str(generation),
                }},
            )

    db.vps_meta.update_one(
        {"_id": "live"},
        {"$set": {
            "runner_id": str(runner_id),
            "generation": str(generation),
            "last_sync": time.time(),
            "file_count": len(current),
            "package_manifest": package_manifest(),
            "status": "syncing",
        }},
        upsert=True,
    )
    return uploaded, len(current)


def restore(db, fs, roots):
    restored = 0
    for doc in db.vps_files.find({"deleted": False}):
        path = doc["path"]
        if not managed(path, roots):
            continue

        fid = doc.get("file_id")
        if not fid:
            continue

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".restore-tmp")
        with open(tmp, "wb") as out:
            out.write(fs.get(fid).read())
        os.replace(tmp, target)

        try:
            os.chmod(target, int(doc.get("mode", 0o600)))
        except OSError:
            pass
        restored += 1

    return restored


def verify_state(db, roots):
    bad = []
    for item in db.vps_files.find({"deleted": False}):
        path = item["path"]
        if not managed(path, roots):
            continue
        try:
            if not os.path.exists(path) or sha256_file(path) != item["sha256"]:
                bad.append(path)
        except OSError:
            bad.append(path)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "mode",
        choices=["sync", "restore", "mirror", "once", "request-cutover",
                 "watch-cutover", "activate"],
    )
    ap.add_argument("--uri", required=True)
    ap.add_argument("--db", default="own_vps")
    ap.add_argument("--runner-id", default=os.getenv("GITHUB_RUN_ID", "unknown"))
    ap.add_argument("--generation", default=os.getenv("VPS_GENERATION", "0"))
    ap.add_argument("--interval", type=int, default=15)
    ap.add_argument("--target-run", default="")
    ap.add_argument("--path", action="append", dest="paths")
    args = ap.parse_args()

    roots = args.paths or DEFAULT_PATHS
    client, db, fs = connect(args.uri, args.db)

    try:
        if args.mode == "restore":
            n = restore(db, fs, roots)
            db.vps_meta.update_one(
                {"_id": "live"},
                {"$set": {
                    "restored_by": str(args.runner_id),
                    "restored_at": time.time(),
                    "status": "restored",
                }},
                upsert=True,
            )
            db.vps_runners.update_one(
                {"_id": str(args.runner_id)},
                {"$set": {
                    "runner_id": str(args.runner_id),
                    "generation": str(args.generation),
                    "status": "restored",
                    "restored_files": n,
                }},
                upsert=True,
            )
            event(db, "restore_completed", args.runner_id, args.generation, restored_files=n)
            print(f"RESTORED_FILES={n}", flush=True)
            return 0

        if args.mode == "request-cutover":
            if not args.target_run:
                raise SystemExit("--target-run is required")

            db.vps_cutover.replace_one(
                {"_id": "current"},
                {
                    "_id": "current",
                    "source_run": str(args.runner_id),
                    "target_run": str(args.target_run),
                    "generation": str(args.generation),
                    "requested_at": time.time(),
                    "status": "requested",
                },
                upsert=True,
            )
            event(
                db, "cutover_requested", args.runner_id, args.generation,
                target_run=str(args.target_run),
            )
            print(f"CUTOVER_REQUESTED target={args.target_run}", flush=True)
            return 0

        if args.mode == "watch-cutover":
            while True:
                doc = db.vps_cutover.find_one({"_id": "current"})
                if (
                    doc
                    and str(doc.get("target_run")) == str(args.runner_id)
                    and doc.get("status") == "requested"
                ):
                    restored = restore(db, fs, roots)
                    bad = verify_state(db, roots)

                    if bad:
                        db.vps_runners.update_one(
                            {"_id": str(args.runner_id)},
                            {"$set": {
                                "status": "verification_failed",
                                "verification_errors": bad[:20],
                            }},
                            upsert=True,
                        )
                        event(
                            db, "cutover_verification_failed",
                            args.runner_id, args.generation,
                            error_count=len(bad),
                        )
                        raise RuntimeError(f"Verification failed for {len(bad)} files")

                    db.vps_runners.update_one(
                        {"_id": str(args.runner_id)},
                        {"$set": {
                            "runner_id": str(args.runner_id),
                            "generation": str(args.generation),
                            "status": "verified",
                            "verified_at": time.time(),
                            "restored_files": restored,
                        }},
                        upsert=True,
                    )
                    db.vps_cutover.update_one(
                        {"_id": "current"},
                        {"$set": {
                            "status": "verified",
                            "verified_at": time.time(),
                        }},
                    )
                    event(
                        db, "cutover_verified",
                        args.runner_id, args.generation,
                        restored_files=restored,
                    )
                    print(f"CUTOVER_VERIFIED restored={restored}", flush=True)
                    return 0

                time.sleep(args.interval)

        if args.mode == "activate":
            doc = db.vps_cutover.find_one({"_id": "current"})
            if (
                not doc
                or str(doc.get("target_run")) != str(args.runner_id)
                or doc.get("status") != "verified"
            ):
                raise RuntimeError("Cutover is not verified for this runner")

            db.vps_meta.update_one(
                {"_id": "live"},
                {"$set": {
                    "active_runner": str(args.runner_id),
                    "generation": str(args.generation),
                    "status": "active",
                    "activated_at": time.time(),
                }},
                upsert=True,
            )
            db.vps_runners.update_one(
                {"_id": str(args.runner_id)},
                {"$set": {
                    "status": "active",
                    "activated_at": time.time(),
                }},
                upsert=True,
            )
            db.vps_cutover.update_one(
                {"_id": "current"},
                {"$set": {
                    "status": "activated",
                    "activated_at": time.time(),
                }},
            )
            event(db, "worker_activated", args.runner_id, args.generation)
            print("CUTOVER_ACTIVATED", flush=True)
            return 0

        if args.mode == "once":
            n, total = sync_once(
                db, fs, roots, args.runner_id, args.generation
            )
            event(
                db, "sync_once_completed",
                args.runner_id, args.generation,
                file_count=total, changed_or_checked=n,
            )
            print(
                f"SYNC_ONCE files={total} changed_or_checked={n}",
                flush=True,
            )
            return 0

        if args.mode == "mirror":
            event(db, "worker_standby_started", args.runner_id, args.generation)
            while True:
                n = restore(db, fs, roots)
                db.vps_runners.update_one(
                    {"_id": str(args.runner_id)},
                    {"$set": {
                        "runner_id": str(args.runner_id),
                        "generation": str(args.generation),
                        "last_mirror": time.time(),
                        "status": "standby",
                        "restored_files": n,
                    }},
                    upsert=True,
                )
                print(f"MIRROR restored={n}", flush=True)
                time.sleep(args.interval)

        event(db, "worker_sync_started", args.runner_id, args.generation)
        while True:
            n, total = sync_once(
                db, fs, roots, args.runner_id, args.generation
            )
            db.vps_runners.update_one(
                {"_id": str(args.runner_id)},
                {"$set": {
                    "runner_id": str(args.runner_id),
                    "generation": str(args.generation),
                    "last_sync": time.time(),
                    "status": "active",
                }},
                upsert=True,
            )
            print(
                f"SYNC files={total} changed_or_checked={n}",
                flush=True,
            )
            time.sleep(args.interval)

    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
