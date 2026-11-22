"""Daily job: pick up new releases of tracked libraries, compile only what is new, re-export the site.

    py -3.11 farm/update.py            # refresh index, plan new versions, run, export
    py -3.11 farm/update.py --dry-run  # only report what is new

Also reports new Arduino-ESP32 core releases. Adding a core column is a scope
decision, so it is reported, not done automatically (edit CORES in common.py).
"""
import argparse
import json
import subprocess
import sys
import urllib.request

import store
from common import PLAN_PATH, CORES, EXAMPLES_PER_LIB, PROJECT, load_json, save_json, db, now, version_key
from prepare import refresh_index

CORE_INDEX = "https://espressif.github.io/arduino-esp32/package_esp32_index.json"


def new_cores():
    req = urllib.request.Request(CORE_INDEX, headers={"User-Agent": "esp32-compat-farm"})
    with urllib.request.urlopen(req, timeout=120) as r:
        idx = json.load(r)
    vs = {p["version"] for pk in idx["packages"] for p in pk["platforms"]}
    newest = max(CORES, key=version_key)
    return sorted((v for v in vs if version_key(v) > version_key(newest)), key=version_key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--plan-only", action="store_true", help="update plan.json and stop (CI runs the compiles)")
    a = ap.parse_args()
    refresh_index()
    store._index = None
    plan = load_json(PLAN_PATH)
    con = db()
    seen = {(r[0], r[1]) for r in con.execute("SELECT lib, lib_version FROM index_seen")}
    added = []
    for lib in plan["libs"]:
        known = [v["version"] for v in lib["versions"]]
        fresh = [v for v in store.versions(lib["name"]) if (lib["name"], v) not in seen and v not in known
                 and version_key(v) > version_key(known[0] if known else "0")]
        for v in sorted(fresh, key=version_key):
            added.append((lib["name"], v))
            if a.dry_run:
                continue
            root = store.ensure(lib["name"], v)
            prefer = lib["versions"][0]["examples"] if lib["versions"] else []
            exs = store.pick_examples(root, EXAMPLES_PER_LIB, prefer, name=lib["name"])
            deps = store.deps_closure(lib["name"], v)
            for dn, dv in deps.items():
                store.ensure(dn, dv)
            lib["versions"].insert(0, {"version": v, "examples": exs, "deps": deps})
            con.execute("INSERT OR IGNORE INTO index_seen VALUES (?,?,?)", (lib["name"], v, now()))
    print("new library releases:", added or "none")
    try:
        nc = new_cores()
        if nc:
            print(f"NEW ARDUINO-ESP32 CORE RELEASES: {nc} (add to CORES in farm/common.py to test them)")
    except Exception as e:
        print("could not check core index:", e)
    if a.dry_run:
        return
    con.commit()
    plan["updated"] = now()
    save_json(PLAN_PATH, plan)
    if a.plan_only:
        return
    py = sys.executable
    if added:
        subprocess.run([py, str(PROJECT / "farm" / "run.py"), "--workers", str(a.workers),
                        "--only", *sorted({n for n, _ in added})], check=False)
    subprocess.run([py, str(PROJECT / "farm" / "run.py"), "--retry-infra", "--workers", str(a.workers)], check=False)
    subprocess.run([py, str(PROJECT / "farm" / "export.py")], check=False)


if __name__ == "__main__":
    main()
