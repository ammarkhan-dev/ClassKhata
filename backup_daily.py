"""ClassKhata - daily backup.  Standard library only.
Copies classkhata.db and every data/t*.db into backups/<YYYY-MM-DD>/ (safe copy, works while the app is running),
keeps the newest KEEP days.   Run:  python backup_daily.py"""
import glob
import os
import shutil
import sqlite3
import sys
from datetime import date

KEEP = 14
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "backups")


def copy_db(src, dst):
    a = sqlite3.connect(src)
    b = sqlite3.connect(dst)
    try:
        a.backup(b)
    finally:
        b.close()
        a.close()


def main():
    day = os.path.join(OUT, date.today().isoformat())
    os.makedirs(day, exist_ok=True)
    srcs = [os.path.join(HERE, "classkhata.db")] + sorted(glob.glob(os.path.join(HERE, "data", "t*.db")))
    ok = bad = 0
    for s in srcs:
        if not os.path.exists(s):
            continue
        try:
            copy_db(s, os.path.join(day, os.path.basename(s)))
            ok += 1
        except Exception as e:
            bad += 1
            print("FAIL", os.path.basename(s), e)
    for d in sorted(x for x in os.listdir(OUT) if len(x) == 10 and x[4] == "-")[:-KEEP]:
        shutil.rmtree(os.path.join(OUT, d), ignore_errors=True)
    print("backup %s: %d ok, %d failed -> %s" % (date.today().isoformat(), ok, bad, day))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
