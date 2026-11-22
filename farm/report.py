"""Nightly report: what tonight's run found.

    python farm/report.py --since <row id before tonight's results> [--run-url URL]

Writes, in the farm dir:
    news.json          new "What's new" entries (new library releases, new breakages, fixes)
    regressions.json   the current set of regressions, to compare against tomorrow
    report.md          the body of the "Farm status" GitHub issue (updated every night, no email)
    alert.md           only when something needs attention (a new breakage or a new core);
                       the workflow posts it as a comment, which emails the owner

Everything here is derived from stored results; it never changes a result.
"""
import argparse
import time

from common import FARM, PLAN_PATH, CHIPS, CORES, BASELINE_CORE, TARGET_CORE, load_json, save_json, db
from news import add_news, load_news

REG_PATH = FARM / "regressions.json"
REPORT = FARM / "report.md"
ALERT = FARM / "alert.md"
CHIP = {"esp32": "ESP32", "esp32s3": "ESP32-S3", "esp32c3": "ESP32-C3"}
BAD = ("fail", "dep_fail")
TABLE_URL = "https://yuvalbloch.com/wild-west/esp32-table/"


def example_status(con):
    """(lib, version, core, chip, example) -> status; a pass with documented board options counts as pass."""
    raw = {}
    for lib, ver, core, chip, ex, opt, st in con.execute(
            "SELECT lib, lib_version, core, chip, example, options, status FROM results"):
        raw.setdefault((lib, ver, core, chip, ex), {})["opt" if opt else "base"] = st
    out = {}
    for k, o in raw.items():
        s = o.get("base", o.get("opt"))
        if s != "pass" and o.get("opt") == "pass":
            s = "pass"
        out[k] = s
    return out


def regressions(es, plan):
    regs = set()
    for l in plan["libs"]:
        for v in l["versions"]:
            for ch in CHIPS:
                if any(es.get((l["name"], v["version"], BASELINE_CORE, ch, ex)) == "pass"
                       and es.get((l["name"], v["version"], TARGET_CORE, ch, ex)) in BAD for ex in v["examples"]):
                    regs.add(f"{l['name']}|{v['version']}|{ch}")
    return regs


def chip_summary(es, lib, ver, core, examples):
    ok, bad = [], []
    for ch in CHIPS:
        ss = [es.get((lib, ver, core, ch, ex)) for ex in examples]
        ss = [s for s in ss if s]
        if ss and all(s == "pass" for s in ss):
            ok.append(CHIP[ch])
        elif any(s in BAD for s in ss):
            bad.append(CHIP[ch])
    return ok, bad


def group(keys):
    """{'lib|ver|chip'} -> {(lib, ver): [chip names]}"""
    out = {}
    for k in sorted(keys):
        lib, ver, ch = k.split("|")
        out.setdefault((lib, ver), []).append(CHIP[ch])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, required=True)
    ap.add_argument("--run-url", default="")
    a = ap.parse_args()
    today = time.strftime("%Y-%m-%d")
    con = db()
    plan = load_json(PLAN_PATH)
    examples = {(l["name"], v["version"]): v["examples"] for l in plan["libs"] for v in l["versions"]}
    newest = {l["name"]: l["versions"][0]["version"] for l in plan["libs"] if l["versions"]}
    es = example_status(con)

    # 1. library releases compiled for the first time tonight
    before = {tuple(r) for r in con.execute("SELECT DISTINCT lib, lib_version FROM results WHERE id <= ?", (a.since,))}
    tonight = [tuple(r) for r in con.execute(
        "SELECT DISTINCT lib, lib_version FROM results WHERE id > ? ORDER BY lib, lib_version", (a.since,))]
    n_new_rows = con.execute("SELECT COUNT(*) FROM results WHERE id > ?", (a.since,)).fetchone()[0]
    for lib, ver in tonight:
        if (lib, ver) in before or (lib, ver) not in examples:
            continue
        ok, bad = chip_summary(es, lib, ver, TARGET_CORE, examples[(lib, ver)])
        if bad:
            text = f"{lib} {ver} released: fails on core {TARGET_CORE} for {', '.join(bad)}" + \
                   (f" (builds on {', '.join(ok)})." if ok else ".")
        elif ok:
            text = f"{lib} {ver} released: builds on core {TARGET_CORE} for {', '.join(ok)}."
        else:
            text = f"{lib} {ver} released: tested; see the table for details."
        add_news("release", text, today)

    # 2. regressions that appeared or disappeared since the last run
    now_regs = regressions(es, plan)
    prev = set(load_json(REG_PATH)) if REG_PATH.exists() else None
    new_regs, fixed = (set(), set()) if prev is None else (now_regs - prev, prev - now_regs)
    for (lib, ver), chips in group(new_regs).items():
        add_news("broken", f"{lib} {ver} no longer builds on core {TARGET_CORE} for {', '.join(chips)} "
                           f"(it builds on {BASELINE_CORE}).", today)
    for (lib, ver), chips in group(fixed).items():
        add_news("fixed", f"{lib} {ver} is no longer broken on core {TARGET_CORE} for {', '.join(chips)}.", today)
    save_json(REG_PATH, sorted(now_regs))

    # 3. the issue body and, when needed, an alert
    todays = [n for n in load_news() if n["date"] == today]
    cores_today = [n for n in todays if n["kind"] == "core"]
    newest_regs = {k for k in now_regs if newest.get(k.split("|")[0]) == k.split("|")[1]}
    total = con.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    lines = [
        "This issue is updated automatically after every run of the compile farm. "
        "You get an email only when a comment is added, which happens when something needs attention "
        "(a library newly broken, or a new Arduino-ESP32 core).",
        "",
        f"**Last run:** {today}" + (f" ([log]({a.run_url}))" if a.run_url else ""),
        f"**Cores in the table:** {', '.join(CORES)} (regressions: {BASELINE_CORE} → {TARGET_CORE})",
        f"**Compiles tonight:** {n_new_rows} · **all compiles:** {total:,}",
        f"**Libraries broken on {TARGET_CORE} (newest version):** {len({k.split('|')[0] for k in newest_regs})}",
        f"**Table:** {TABLE_URL}",
        "",
        "### Tonight",
    ]
    lines += [f"- {n['text']}" for n in todays] or ["- No new library releases and no changes."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    alert = [n for n in todays if n["kind"] in ("core", "broken")]
    if alert:
        ALERT.write_text("Something needs a look:\n\n" + "\n".join(f"- {n['text']}" for n in alert) +
                         f"\n\nTable: {TABLE_URL}" + (f" · run: {a.run_url}" if a.run_url else "") + "\n",
                         encoding="utf-8")
    elif ALERT.exists():
        ALERT.unlink()
    print(REPORT.read_text(encoding="utf-8"))
    print("alert:", "yes" if alert else "no", f"({len(cores_today)} core events)")


if __name__ == "__main__":
    main()
