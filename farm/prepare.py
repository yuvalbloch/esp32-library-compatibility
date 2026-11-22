"""Build the test plan: which library versions and which example sketches to compile.

    py -3.11 farm/prepare.py            # wave-1 libraries from selection.json
    py -3.11 farm/prepare.py --refresh  # re-download library_index.json first

Writes FARM/plan.json. Library choice comes from selection.json (the approved
selection plan); version choice is 'latest + 3 previous stable releases'.
"""
import argparse
import sys
import urllib.request
import gzip
import shutil
from concurrent.futures import ThreadPoolExecutor

import store
from common import (INDEX_DIR, PLAN_PATH, SELECTION, VERSIONS_PER_LIB, EXAMPLES_PER_LIB,
                    load_json, save_json, now, db)

INDEX_URL = "https://downloads.arduino.cc/libraries/library_index.json.gz"


def refresh_index():
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    gz = INDEX_DIR / "library_index.json.gz"
    req = urllib.request.Request(INDEX_URL, headers={"User-Agent": "esp32-compat-farm"})
    with urllib.request.urlopen(req, timeout=300) as r, open(gz, "wb") as f:
        shutil.copyfileobj(r, f)
    with gzip.open(gz) as src, open(INDEX_DIR / "library_index.json", "wb") as dst:
        shutil.copyfileobj(src, dst)


def selected_libs():
    sel = load_json(SELECTION)
    libs = []
    for group in ("untested_selected", "espressif_tested"):
        for e in sel[group]:
            libs.append({
                "name": e["name"], "category": e["category"], "repo": e.get("repo", ""),
                "espressif_tested": bool(e.get("espressif_tested")) or group == "espressif_tested",
                "score": e["score"], "risk_raw": e["risk_raw"], "risk_reasons": e.get("risk_reasons", []),
                "stars": e.get("stars"),
            })
    return libs


def plan_lib(lib, versions=None):
    name = lib["name"]
    vs = versions or store.pick_versions(name, VERSIONS_PER_LIB)
    out, prefer = [], []
    for v in vs:   # newest first: its example picks are preferred for older versions
        try:
            root = store.ensure(name, v)
        except Exception as e:  # download problem: recorded, the version is skipped
            print(f"  ! {name}@{v}: {e}", file=sys.stderr)
            continue
        exs = store.pick_examples(root, EXAMPLES_PER_LIB, prefer, name=name)
        if not prefer:
            prefer = exs
        deps = store.deps_closure(name, v)
        for dn, dv in deps.items():
            try:
                store.ensure(dn, dv)
            except Exception as e:
                print(f"  ! dep {dn}@{dv}: {e}", file=sys.stderr)
        out.append({"version": v, "examples": exs, "deps": deps})
    lib = dict(lib, versions=out)
    print(f"  {name}: {', '.join(x['version'] for x in out)} | examples: {prefer}")
    return lib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download the Library Manager index")
    ap.add_argument("--only", nargs="*", help="limit to these library names")
    a = ap.parse_args()
    if a.refresh or not (INDEX_DIR / "library_index.json").exists():
        refresh_index()
    store.index()
    libs = selected_libs()
    if a.only:
        libs = [l for l in libs if l["name"] in a.only]
    missing = [l["name"] for l in libs if l["name"] not in store.index()]
    if missing:
        print("not in index:", missing)
    libs = [l for l in libs if l["name"] in store.index()]
    with ThreadPoolExecutor(8) as ex:
        planned = list(ex.map(plan_lib, libs))
    plan = {"generated": now(), "libs": planned}
    save_json(PLAN_PATH, plan)
    con = db()
    for l in planned:
        for v in l["versions"]:
            con.execute("INSERT OR IGNORE INTO index_seen VALUES (?,?,?)", (l["name"], v["version"], now()))
    con.commit()
    n_ex = sum(len(v["examples"]) for l in planned for v in l["versions"])
    print(f"\nplan: {len(planned)} libraries, {sum(len(l['versions']) for l in planned)} versions, "
          f"{n_ex} (version, example) pairs -> {PLAN_PATH}")
    noex = [l["name"] for l in planned if not any(v["examples"] for v in l["versions"])]
    if noex:
        print("no examples found:", noex)


if __name__ == "__main__":
    main()
