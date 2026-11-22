"""Daily job: pick up new releases of tracked libraries, compile only what is new, re-export the site.

    py -3.11 farm/update.py            # refresh index, plan new versions, run, export
    py -3.11 farm/update.py --dry-run  # only report what is new

Also follows new Arduino-ESP32 core releases: each column is the newest stable release of a
core line (2.0, 3.0, 3.3, 4.x; see CORE_LINES in common.py). When a line gets a newer release,
cores.json is updated and the next compile step runs the full plan on it. Results for the old
release stay in results.db.
"""
import argparse
import json
import subprocess
import sys
import urllib.request

import store
from common import (PLAN_PATH, CORES_PATH, CORE_LINES, EXAMPLES_PER_LIB, PROJECT, load_json, save_json, db, now,
                    version_key, is_prerelease, core_line, load_core_map)
from news import add_news
from prepare import refresh_index

CORE_INDEX = "https://espressif.github.io/arduino-esp32/package_esp32_index.json"


def core_updates():
    """{line: newer stable release} for core lines that Espressif has moved forward."""
    req = urllib.request.Request(CORE_INDEX, headers={"User-Agent": "esp32-compat-farm"})
    with urllib.request.urlopen(req, timeout=120) as r:
        idx = json.load(r)
    current = load_core_map()
    newest = {}
    for pk in idx["packages"]:
        for p in pk["platforms"]:
            v = p["version"]
            line = core_line(v)
            if line and not is_prerelease(v) and version_key(v) > version_key(newest.get(line, current[line])):
                newest[line] = v
    return newest


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
                 and not is_prerelease(v) and version_key(v) > version_key(known[0] if known else "0")]
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
        moved = core_updates()
    except Exception as e:
        moved = {}
        print("could not check core index:", e)
    if moved:
        print("new Arduino-ESP32 core releases:", moved)
    if a.dry_run:
        return
    if moved:
        cmap = load_core_map()
        for line, v in sorted(moved.items()):
            add_news("core", f"Arduino-ESP32 core {v} released: it replaces {cmap[line]} in the table. "
                             f"Every library is being compiled against it.")
            cmap[line] = v
        save_json(CORES_PATH, {l: cmap[l] for l in CORE_LINES})
    if not CORES_PATH.exists():
        save_json(CORES_PATH, load_core_map())
    con.commit()
    plan["updated"] = now()
    save_json(PLAN_PATH, plan)
    if a.plan_only:
        return
    py = sys.executable
    if moved:   # local mode: install the new core(s); run.py below then compiles the full plan on them
        subprocess.run([py, str(PROJECT / "farm" / "setup_cores.py"), *moved.values()], check=False)
    if added:
        subprocess.run([py, str(PROJECT / "farm" / "run.py"), "--workers", str(a.workers),
                        "--only", *sorted({n for n, _ in added})], check=False)
    subprocess.run([py, str(PROJECT / "farm" / "run.py"), "--retry-infra", "--workers", str(a.workers)], check=False)
    subprocess.run([py, str(PROJECT / "farm" / "export.py")], check=False)


if __name__ == "__main__":
    main()
