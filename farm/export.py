"""Export results.db -> site/data/results.json + site/logs/ (plain-text compile logs).

    py -3.11 farm/export.py

The site only ever shows statuses that are stored in results.db, and every
status links to the log it came from.
"""
import gzip
import json
import shutil

from common import (SITE, LOGS, PLAN_PATH, CORES, CHIPS, BASELINE_CORE, TARGET_CORE, BIG_APP_OPTION,
                    load_json, save_json, db, now)

MAX_LOG = 400_000   # characters kept per published log (head + tail)


def export_logs(rows):
    out_dir = SITE / "logs"
    n = 0
    for r in rows:
        src = LOGS / r["log_file"]
        dst = out_dir / r["log_file"].replace(".log.gz", ".txt")
        if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(src, "rt", encoding="utf-8", errors="replace") as f:
            text = f.read()
        if len(text) > MAX_LOG:
            text = text[:MAX_LOG // 2] + "\n\n... [log shortened for the website; middle part removed] ...\n\n" + text[-MAX_LOG // 2:]
        dst.write_text(text, encoding="utf-8")
        n += 1
    return n


def main():
    con = db()
    rows = [dict(r) for r in con.execute("SELECT * FROM results ORDER BY lib, lib_version, core, chip, example, options")]
    plan = load_json(PLAN_PATH)
    libs = []
    for l in plan["libs"]:
        libs.append({
            "name": l["name"], "category": l["category"], "repo": l["repo"].removesuffix(".git"),
            "espressif_tested": l["espressif_tested"], "risk": l["risk_raw"], "risk_reasons": l["risk_reasons"],
            "versions": [v["version"] for v in l["versions"]],
            "examples": {v["version"]: v["examples"] for v in l["versions"]},
        })
    known = {l["name"] for l in libs}
    lib_idx = {l["name"]: i for i, l in enumerate(libs)}
    out_rows = []
    for r in rows:
        if r["lib"] not in known:
            continue
        out_rows.append([lib_idx[r["lib"]], r["lib_version"], r["core"], r["chip"],
                         r["example"].removeprefix("examples/"), r["options"], r["status"],
                         r["first_error"] or "", r["root_cause"] or "", r["log_file"].replace(".log.gz", ".txt"),
                         json.loads(r["deps"] or "{}"), r["created_at"][:10]])
    data = {
        "generated": now(), "cores": CORES, "chips": CHIPS, "baseline": BASELINE_CORE, "target": TARGET_CORE,
        "big_app_option": BIG_APP_OPTION, "cli_version": rows[0]["cli_version"] if rows else "",
        "row_fields": ["lib", "version", "core", "chip", "example", "options", "status", "first_error",
                       "root_cause", "log", "deps", "date"],
        "libs": libs, "rows": out_rows,
    }
    save_json(SITE / "data" / "results.json", data)
    n = export_logs(rows)
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"exported {len(out_rows)} results ({counts}), {n} new logs -> {SITE}")


if __name__ == "__main__":
    main()
