"""Run the compile farm over FARM/plan.json.

    py -3.11 farm/run.py                     # everything not yet done (resumable)
    py -3.11 farm/run.py --latest-only       # newest version of each library first
    py -3.11 farm/run.py --only FastLED --cores 3.3.12 4.0.0 --chips esp32
    py -3.11 farm/run.py --limit 20          # pilot
    py -3.11 farm/run.py --retry-infra       # re-run cells that hit a farm problem

Each compile becomes one row in results.db plus one gzipped log. Rows are
never overwritten, except `infra_error` rows (the farm failed, not the code).
"""
import argparse
import gzip
import hashlib
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import store
from classify import classify, missing_header
from common import (CLI, FARM, BUILDS, LOGS, PLAN_PATH, CORES, CHIPS, BASELINE_CORE, TARGET_CORE,
                    BIG_APP_OPTION, COMPILE_TIMEOUT, core_config, core_platform_dir, child_env,
                    load_json, db, now)

CORE_ORDER = [BASELINE_CORE, TARGET_CORE] + [c for c in CORES if c not in (BASELINE_CORE, TARGET_CORE)]
MAX_HEADER_FIXES = 4
IDF_LIKE = ("esp_", "esp32", "soc", "hal", "driver", "freertos", "sdkconfig", "rom", "lwip", "mbedtls", "psa",
            "nvs", "wifi", "bt", "sys", "nimble", "host", "tinyusb", "tusb", "arduino.h", "pins_arduino")

_db_lock = threading.Lock()
_con = None


def con():
    global _con
    if _con is None:
        _con = db()
        _con.close()
        import sqlite3
        _con = sqlite3.connect(str(FARM / "results.db"), timeout=60, check_same_thread=False)
        _con.row_factory = sqlite3.Row
    return _con


# ---------------- bundled (core) libraries ----------------
_bundled = {}


def bundled(core):
    """(library names, header names) shipped inside a core."""
    if core not in _bundled:
        names, headers = set(), set()
        libdir = core_platform_dir(core) / "libraries"
        for d in libdir.iterdir() if libdir.exists() else []:
            props = d / "library.properties"
            if props.exists():
                for line in props.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("name="):
                        names.add(line[5:].strip())
            names.add(d.name)
            for h in d.rglob("*.h"):
                headers.add(h.name)
        _bundled[core] = (names, headers)
    return _bundled[core]


def protected_headers():
    hs = set()
    for c in CORES:
        hs |= bundled(c)[1]
    return hs


_providers = None


def provider_candidates(header, lib):
    """Libraries that may provide `header`, for examples that use a library their own library does not
    declare. Never for ESP-IDF/core headers or headers a core-bundled library provides."""
    global _providers
    if "/" in header or "\\" in header or header.lower().startswith(IDF_LIKE) or header in protected_headers():
        return []
    if _providers is None:
        _providers = store.header_providers()
    return [c for c in store.header_candidates(header, _providers) if c != lib]


def find_provider(header, lib, libs):
    """First candidate (newest version) that really contains the header. -> (name, version) or None."""
    for c in provider_candidates(header, lib)[:6]:
        if c in libs:
            continue
        try:
            v = store.resolve_dep_version(c)
            root = store.ensure(c, v)
        except Exception:
            continue
        if store.has_header(root, header):
            return c, v
    return None


# ---------------- jobs ----------------
def build_jobs(plan, cores, chips, latest_only=False, only=None):
    jobs = []
    for lib in plan["libs"]:
        if only and lib["name"] not in only:
            continue
        for vrank, v in enumerate(lib["versions"]):
            if latest_only and vrank > 0:
                continue
            for ex in v["examples"]:
                for core in cores:
                    for chip in chips:
                        jobs.append({
                            "lib": lib["name"], "version": v["version"], "example": ex, "core": core, "chip": chip,
                            "deps": v["deps"], "risk": lib["risk_raw"], "vrank": vrank,
                        })
    jobs.sort(key=lambda j: (j["vrank"], CORE_ORDER.index(j["core"]), CHIPS.index(j["chip"]) if j["chip"] in CHIPS else 9,
                             -j["risk"], j["lib"], j["example"]))
    return jobs


MAX_SHARDS_PER_CORE = 16


def shard_of(job, n):
    """Stable chunk number. All chips of one (library, version, example) land in the same chunk."""
    k = f"{job['lib']}|{job['version']}|{job['example']}".encode()
    return int(hashlib.sha1(k).hexdigest(), 16) % n


def done_keys(retry_infra):
    q = "SELECT lib, lib_version, core, chip, example FROM results WHERE options=''"
    if retry_infra:
        q += " AND status != 'infra_error'"
    with _db_lock:
        return {tuple(r) for r in con().execute(q)}


def get_extras(lib, version, example):
    with _db_lock:
        r = con().execute("SELECT deps FROM extras WHERE lib=? AND lib_version=? AND example=?",
                          (lib, version, example)).fetchone()
    return json.loads(r[0]) if r else {}


def set_extras(lib, version, example, extras):
    with _db_lock:
        con().execute("INSERT OR REPLACE INTO extras VALUES (?,?,?,?)", (lib, version, example, json.dumps(extras)))
        con().commit()


# ---------------- one compile ----------------
_cli_version = None


def cli_version():
    global _cli_version
    if _cli_version is None:
        _cli_version = subprocess.run([str(CLI), "version"], capture_output=True, text=True).stdout.strip()
    return _cli_version


def compile_once(job, libs, options, build_dir):
    """libs: {name: version}. Returns (returncode, log, timed_out, seconds, dep_roots)."""
    root = store.ensure(job["lib"], job["version"])
    src = root / job["example"]
    # Copy the example into this worker's own folder: arduino-cli keys its build folder on the sketch
    # path, and we must not pass --build-path (that disables the precompiled-core cache: 130s -> 25s).
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
    sketch = build_dir / src.name
    shutil.copytree(src, sketch)
    dep_dirs = [store.lib_dir(n, v) for n, v in libs.items()]
    fqbn = f"esp32:esp32:{job['chip']}" + (f":{options}" if options else "")
    cmd = [str(CLI), "--config-file", str(core_config(job["core"])), "compile", "--fqbn", fqbn,
           "--jobs", "2", "--no-color",
           "--libraries", str(store.lib_dir(job["lib"], job["version"]))]
    for d in dep_dirs:
        cmd += ["--libraries", str(d)]
    cmd.append(str(sketch))
    header = (f"# library: {job['lib']} {job['version']}\n# example: {job['example']}\n# core: esp32:esp32@{job['core']}\n"
              f"# fqbn: {fqbn}\n# other libraries given to the compiler: {json.dumps(libs)}\n# arduino-cli: {cli_version()}\n"
              f"# date: {now()}\n# command: {subprocess.list2cmdline(cmd)}\n\n")
    t0 = time.time()
    timed_out = False
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=COMPILE_TIMEOUT, env=child_env())
        rc, out = p.returncode, p.stdout + b"\n" + p.stderr
    except subprocess.TimeoutExpired as e:
        rc, out, timed_out = -1, (e.stdout or b"") + b"\n" + (e.stderr or b""), True
    log = header + out.decode("utf-8", errors="replace") + f"\n# exit code: {rc}\n"
    return rc, log, timed_out, time.time() - t0, [store.lib_root(n, v) for n, v in libs.items()]


def save_row(job, options, res, libs, seconds, log):
    key = f"{job['lib']}|{job['version']}|{job['core']}|{job['chip']}|{job['example']}|{options}"
    h = hashlib.sha1(key.encode()).hexdigest()[:16]
    rel = f"{job['core']}/{h}.log.gz"
    path = LOGS / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    log = log.replace(str(Path.home()), "<home>")
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(log)
    with _db_lock:
        c = con()
        c.execute("DELETE FROM results WHERE lib=? AND lib_version=? AND core=? AND chip=? AND example=? AND options=? "
                  "AND status='infra_error'", (job["lib"], job["version"], job["core"], job["chip"], job["example"], options))
        c.execute("INSERT OR IGNORE INTO results (lib, lib_version, core, chip, example, options, status, first_error, "
                  "error_file, signature, root_cause, deps, duration_s, log_file, cli_version, created_at) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (job["lib"], job["version"], job["core"], job["chip"], job["example"], options, res["status"],
                   res["first_error"], res["error_file"], res["signature"], res["root_cause"], json.dumps(libs),
                   round(seconds, 1), rel, cli_version(), now()))
        c.commit()


_board_options = None


def lib_board_option(lib, chip):
    """Board options the library documents as required on this chip (farm/board_options.json), or None."""
    global _board_options
    if _board_options is None:
        p = Path(__file__).with_name("board_options.json")
        _board_options = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    o = _board_options.get(lib)
    return o.get(chip) if isinstance(o, dict) else None


def run_job(job, build_dir):
    names, _ = bundled(job["core"])
    libs = {n: v for n, v in job["deps"].items() if n not in names}
    extras = get_extras(job["lib"], job["version"], job["example"])
    libs.update({n: v for n, v in extras.items() if n not in names})
    for n, v in libs.items():
        store.ensure(n, v)
    new_extras = dict(extras)
    for attempt in range(MAX_HEADER_FIXES + 2):
        rc, log, timed_out, secs, dep_roots = compile_once(job, libs, "", build_dir)
        res = classify(rc, log, timed_out, dep_roots)
        if res["status"] == "infra_error" and attempt == 0:
            continue  # one immediate retry for farm hiccups
        h = missing_header(res["first_error"]) if res["status"] in ("fail", "dep_fail") else None
        if h and attempt < MAX_HEADER_FIXES:
            found = find_provider(h, job["lib"], libs)
            # (a core library with the same *name* is no reason to refuse: e.g. the core's "Ethernet"
            #  is ETH.h for the chip's own MAC and does not provide Ethernet.h; provider_candidates already
            #  refuses headers that any core library really provides)
            if found:
                prov, pv = found
                try:
                    for dn, dv in store.deps_closure(prov, pv, skip=names).items():
                        store.ensure(dn, dv)
                        libs.setdefault(dn, dv)
                        new_extras.setdefault(dn, dv)
                except Exception:
                    break
                libs[prov] = pv
                new_extras[prov] = pv
                continue
        break
    if new_extras != extras:
        set_extras(job["lib"], job["version"], job["example"], new_extras)
    save_row(job, "", res, libs, secs, log)
    results = [res["status"]]
    retry = None
    if res["status"] == "config" and "too big" in (res["signature"] or ""):
        retry = BIG_APP_OPTION
    elif res["status"] not in ("pass", "infra_error") and lib_board_option(job["lib"], job["chip"]):
        retry = lib_board_option(job["lib"], job["chip"])
    if retry:
        rc, log2, to2, secs2, dep_roots = compile_once(job, libs, retry, build_dir)
        res2 = classify(rc, log2, to2, dep_roots)
        save_row(job, retry, res2, libs, secs2, log2)
        results.append(f"{res2['status']} ({retry})")
    shutil.rmtree(build_dir, ignore_errors=True)
    return res, results, secs


# ---------------- warm-up: build each core once per chip so the core cache exists ----------------
def warm(cores, chips):
    def one(core, chip):
        marker = FARM / "cache" / f".warm-{core}-{chip}"
        if marker.exists():
            return None
        name = f"warm_{chip}"
        sk = FARM / "warm" / name
        sk.mkdir(parents=True, exist_ok=True)
        (sk / f"{name}.ino").write_text("void setup(){}\nvoid loop(){}\n")
        t0 = time.time()
        p = subprocess.run([str(CLI), "--config-file", str(core_config(core)), "compile", "--fqbn",
                            f"esp32:esp32:{chip}", str(sk)], capture_output=True, text=True, env=child_env())
        print(f"warm-up {core} {chip}: {'ok' if p.returncode == 0 else 'FAILED'} ({time.time() - t0:.0f}s)", flush=True)
        if p.returncode != 0:
            return f"core {core} cannot build an empty sketch for {chip}:\n" + (p.stdout + p.stderr)[-3000:]
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(now())
        return None

    with ThreadPoolExecutor(6) as ex:
        errs = [e for e in ex.map(lambda cc: one(*cc), [(c, ch) for c in cores for ch in chips]) if e]
    if errs:
        sys.exit("\n\n".join(errs) + "\nfix the farm before running")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--cores", nargs="*", default=CORES)
    ap.add_argument("--chips", nargs="*", default=CHIPS)
    ap.add_argument("--latest-only", action="store_true")
    ap.add_argument("--retry-infra", action="store_true")
    ap.add_argument("--shard", help="I/N: run only chunk I of N (chunks keep each library version+example together)")
    ap.add_argument("--list-pending", type=int, metavar="N",
                    help="print a CI matrix of chunks with ~N pending compiles each, then exit")
    a = ap.parse_args()

    only = [n.strip() for x in (a.only or []) for n in x.split(",") if n.strip()] or None
    plan = load_json(PLAN_PATH)
    done = done_keys(a.retry_infra)
    jobs = [j for j in build_jobs(plan, a.cores, a.chips, a.latest_only, only)
            if (j["lib"], j["version"], j["core"], j["chip"], j["example"]) not in done]

    if a.list_pending:
        # CI: print a GitHub Actions matrix of (core, shard) chunks that have work, ~N compiles each
        per = a.list_pending
        out = []
        for core in a.cores:
            n_core = sum(1 for j in jobs if j["core"] == core)
            if not n_core:
                continue
            nsh = min(MAX_SHARDS_PER_CORE, -(-n_core // per))
            for i in range(nsh):
                if any(j["core"] == core and shard_of(j, nsh) == i for j in jobs):
                    out.append({"core": core, "shard": i, "nshards": nsh})
        print(json.dumps(out))
        print(f"{len(jobs)} pending compiles in {len(out)} chunks", file=sys.stderr)
        return
    if a.shard:
        i, n = map(int, a.shard.split("/"))
        jobs = [j for j in jobs if shard_of(j, n) == i]

    store.index()
    (FARM / "tmp").mkdir(parents=True, exist_ok=True)
    warm(a.cores, a.chips)
    if a.limit:
        jobs = jobs[:a.limit]
    total = len(jobs)
    print(f"{total} compiles to run with {a.workers} workers", flush=True)
    free = queue.Queue()
    for i in range(a.workers):
        free.put(BUILDS / f"w{i}")
    counts, t_start, n = {}, time.time(), 0

    def worker(job):
        bd = free.get()
        try:
            return job, run_job(job, bd)
        except Exception as e:  # a farm bug must not kill the run; record nothing, report it
            return job, e
        finally:
            free.put(bd)

    with ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(worker, j) for j in jobs]
        for f in as_completed(futs):
            job, out = f.result()
            n += 1
            if isinstance(out, Exception):
                print(f"[{n}/{total}] FARM ERROR {job['lib']}@{job['version']} {job['core']} {job['chip']}: {out!r}", flush=True)
                counts["farm_error"] = counts.get("farm_error", 0) + 1
                continue
            res, statuses, secs = out
            counts[statuses[0]] = counts.get(statuses[0], 0) + 1
            el = time.time() - t_start
            eta = el / n * (total - n)
            print(f"[{n}/{total}] {'/'.join(statuses):18} {job['lib']}@{job['version']} {job['core']} {job['chip']} "
                  f"{job['example'].replace('examples/', '')} ({secs:.0f}s) eta {eta / 60:.0f}m"
                  + (f"  <- {res['first_error'][:90]}" if res["first_error"] else ""), flush=True)
            if n % 10 == 0 or n == total:
                (FARM / "progress.json").write_text(json.dumps(
                    {"done": n, "total": total, "counts": counts, "elapsed_min": round(el / 60, 1),
                     "eta_min": round(eta / 60, 1), "updated": now()}))
    print("summary:", counts)


if __name__ == "__main__":
    main()
