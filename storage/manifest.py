#!/usr/bin/env python3
import hashlib, json, os, stat, sys
from pathlib import Path

ROOTS = [Path("/opt/vps-data"), Path("/root/.pm2")]
EXCLUDE = {"/proc","/sys","/dev","/run","/tmp","/var/lib/apt/lists"}

def digest(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""): h.update(b)
    return h.hexdigest()

items=[]
for root in ROOTS:
    if not root.exists(): continue
    for base, dirs, files in os.walk(root, followlinks=False):
        base=os.path.abspath(base)
        dirs[:] = [d for d in dirs if os.path.abspath(os.path.join(base,d)) not in EXCLUDE]
        for name in files:
            p=Path(base)/name
            try:
                s=p.stat()
                if stat.S_ISREG(s.st_mode):
                    items.append({"path":str(p),"sha256":digest(p),"size":s.st_size,"mode":stat.S_IMODE(s.st_mode)})
            except OSError:
                pass
print(json.dumps({"files":items}, separators=(",",":")))
