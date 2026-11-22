"""Re-apply the current classification rules to the stored logs of every non-passing result.

    py -3.11 farm/reclassify.py [--dry-run]

The compile log and its exit code are the fact; the status is derived from them by the fixed rules
in classify.py. When a rule changes, this brings older rows in line with it. It never touches a
`pass` (exit code 0 is always pass) and can never turn a failed build into a pass.
"""
import argparse
import gzip
import json
import re
from collections import Counter
from pathlib import Path

import store
from classify import classify
from common import FARM, LOGS, db

EXIT = re.compile(r"^# exit code: (-?\d+)\s*$", re.M)
FARM_IN_LOG = re.compile(r"^# command: (.+?)[\\/]bin[\\/]arduino-cli", re.M)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    con = db()
    rows = [dict(r) for r in con.execute(
        "SELECT * FROM results WHERE status NOT IN ('pass', 'infra_error')")]
    home = str(Path.home())
    changes = Counter()
    for r in rows:
        path = LOGS / (r["log_file"] or "")
        if not r["log_file"] or not path.is_file():
            continue
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            log = f.read()
        m = EXIT.findall(log)
        rc = int(m[-1]) if m else 1
        if rc == 0:
            continue   # never re-derive a status for a build that succeeded
        # dependency folders as the compiler saw them: the farm directory written in the log's own
        # command line (it differs between machines) + each dependency's place in the store
        fm = FARM_IN_LOG.search(log)
        prefix = fm.group(1) if fm else str(FARM).replace(home, "<home>")
        roots = [prefix + "/" + store.lib_root(n, v).relative_to(FARM).as_posix()
                 for n, v in json.loads(r["deps"] or "{}").items()]
        res = classify(rc, log, r["first_error"] == "compile timed out", roots)
        if res["status"] in (None, "pass", "infra_error"):
            continue
        if (res["status"], res["root_cause"]) == (r["status"], r["root_cause"]):
            continue
        changes[(r["status"], res["status"], res["root_cause"])] += 1
        if not a.dry_run:
            con.execute("UPDATE results SET status=?, first_error=?, error_file=?, signature=?, root_cause=? "
                        "WHERE id=?", (res["status"], res["first_error"], res["error_file"], res["signature"],
                                       res["root_cause"], r["id"]))
    con.commit()
    for (old, new, rc), n in changes.most_common():
        print(f"{n:5}  {old} -> {new}  [{rc}]")
    print(f"reclassified {sum(changes.values())} of {len(rows)} non-passing results"
          + (" (dry run)" if a.dry_run else ""))


if __name__ == "__main__":
    main()
