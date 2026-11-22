"""Glue for the GitHub Actions farm (.github/workflows/farm.yml).

State between runs lives on the `results` branch of this repository:
    results.db   every result row (immutable facts)
    plan.json    the test plan
    logs/        every compile log (gzipped)

    python farm/ci.py load-state [--logs]   # results branch -> $ESP32FARM
    python farm/ci.py maxid                 # highest row id (before a chunk runs)
    python farm/ci.py pack-results OUT ID   # rows with id > ID + their logs -> OUT/
    python farm/ci.py merge-results DIR...  # merge chunk outputs into results.db + logs
    python farm/ci.py save-state            # $ESP32FARM -> results branch (commit + push)
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from common import FARM, LOGS, PLAN_PATH, DB_PATH, PROJECT, db

STATE = PROJECT / "state"          # git worktree of the results branch
BRANCH = "results"
COLS = ["lib", "lib_version", "core", "chip", "example", "options", "status", "first_error", "error_file",
        "signature", "root_cause", "deps", "duration_s", "log_file", "cli_version", "created_at"]


def git(*args, cwd=PROJECT, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True)


def load_state(with_logs=False):
    FARM.mkdir(parents=True, exist_ok=True)
    if STATE.exists():
        return _copy_in(with_logs)
    if git("fetch", "--depth=1", "origin", BRANCH, check=False).returncode != 0:
        print("no results branch yet: starting fresh")
        return
    git("worktree", "add", "--detach", str(STATE), f"origin/{BRANCH}")
    _copy_in(with_logs)


def _copy_in(with_logs):
    for name in ("results.db", "plan.json"):
        if (STATE / name).exists():
            shutil.copy2(STATE / name, FARM / name)
    if with_logs and (STATE / "logs").exists():
        shutil.copytree(STATE / "logs", LOGS, dirs_exist_ok=True)
    n = db().execute("SELECT COUNT(*) FROM results").fetchone()[0]
    print(f"loaded state: {n} results")


def maxid():
    print(db().execute("SELECT COALESCE(MAX(id), 0) FROM results").fetchone()[0])


def pack_results(out, since):
    out = Path(out)
    (out / "logs").mkdir(parents=True, exist_ok=True)
    con = db()
    rows = [dict(r) for r in con.execute(f"SELECT {', '.join(COLS)} FROM results WHERE id > ?", (int(since),))]
    extras = [list(r) for r in con.execute("SELECT lib, lib_version, example, deps FROM extras")]
    for r in rows:
        dst = out / "logs" / r["log_file"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LOGS / r["log_file"], dst)
    (out / "rows.json").write_text(json.dumps({"rows": rows, "extras": extras}))
    print(f"packed {len(rows)} results")


def merge_results(dirs):
    con = db()
    total = 0
    for d in map(Path, dirs):
        f = d / "rows.json"
        if not f.exists():
            continue
        data = json.loads(f.read_text())
        for r in data["rows"]:
            key = (r["lib"], r["lib_version"], r["core"], r["chip"], r["example"], r["options"])
            con.execute("DELETE FROM results WHERE lib=? AND lib_version=? AND core=? AND chip=? AND example=? "
                        "AND options=? AND status='infra_error'", key)
            cur = con.execute(f"INSERT OR IGNORE INTO results ({', '.join(COLS)}) VALUES ({', '.join('?' * len(COLS))})",
                              [r[c] for c in COLS])
            total += cur.rowcount
        for e in data["extras"]:
            con.execute("INSERT OR IGNORE INTO extras VALUES (?,?,?,?)", e)
        if (d / "logs").exists():
            shutil.copytree(d / "logs", LOGS, dirs_exist_ok=True)
    con.commit()
    print(f"merged {total} new results")


def save_state():
    if not STATE.exists():
        git("worktree", "add", "--orphan", "-b", BRANCH, str(STATE))
    for name in ("results.db", "plan.json"):
        if (FARM / name).exists():
            shutil.copy2(FARM / name, STATE / name)
    if LOGS.exists():
        shutil.copytree(LOGS, STATE / "logs", dirs_exist_ok=True)
    (STATE / "README.md").write_text(
        "# Results data\n\nMachine-written by the compile farm. `results.db` (SQLite) holds every result; "
        "`logs/` holds every compile log. See `docs/methodology.md` on the main branch.\n")
    git("add", "-A", cwd=STATE)
    if not git("status", "--porcelain", cwd=STATE).stdout.strip():
        print("state unchanged")
        return
    n = db().execute("SELECT COUNT(*) FROM results").fetchone()[0]
    git("-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit", "-q", "-m", f"Results: {n} compiles", cwd=STATE)
    git("push", "origin", f"HEAD:refs/heads/{BRANCH}", cwd=STATE)
    print(f"saved state: {n} results")


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "load-state":
        load_state("--logs" in args)
    elif cmd == "maxid":
        maxid()
    elif cmd == "pack-results":
        pack_results(*args)
    elif cmd == "merge-results":
        merge_results(args)
    elif cmd == "save-state":
        save_state()
    else:
        sys.exit(__doc__)
