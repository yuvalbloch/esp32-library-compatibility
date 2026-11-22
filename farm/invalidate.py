"""Remove results that a *farm* bug produced, so they are compiled again.

    py -3.11 farm/invalidate.py --missing-header Adafruit_GFX.h SoftwareSerial.h

Use only when the farm set the build up wrongly (for example it gave the compiler the wrong library
for a header); never to change a result the farm set up correctly. Every use is listed in
docs/methodology.md ("Corrections"). The cached example extras for the affected sketches are
cleared too, so the dependency search runs again.
"""
import argparse

from common import db


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--missing-header", nargs="+", required=True,
                    help="drop failed results whose first error is this header missing")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    con = db()
    keys = set()
    for h in a.missing_header:
        for r in con.execute("SELECT lib, lib_version, core, chip, example FROM results "
                             "WHERE status IN ('fail', 'dep_fail') AND first_error LIKE ?", (h + ": No such file%",)):
            keys.add(tuple(r))
    sketches = {(k[0], k[1], k[4]) for k in keys}
    print(f"{len(keys)} results in {len(sketches)} sketches")
    if a.dry_run:
        return
    for lib, ver, core, chip, ex in keys:
        con.execute("DELETE FROM results WHERE lib=? AND lib_version=? AND core=? AND chip=? AND example=?",
                    (lib, ver, core, chip, ex))
    for lib, ver, ex in sketches:
        con.execute("DELETE FROM extras WHERE lib=? AND lib_version=? AND example=?", (lib, ver, ex))
    con.commit()


if __name__ == "__main__":
    main()
