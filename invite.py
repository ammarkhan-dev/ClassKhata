"""BatchBook - sign-up invite codes (one-time, expiring).
Owner commands (run in ~/classkhata):
  python invite.py new "Sharma Classes"      -> makes a code valid for 14 days   (add a number for other days)
  python invite.py list                       -> shows all codes and who used them
  python invite.py revoke ABCD-EFGH           -> cancels a code
"""
import re, secrets, sqlite3, sys, time

DB = "classkhata.db"
ALPHA = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
DAYS = 14


def _con():
    try:
        import tenant
        c = tenant.raw_connect(DB)
    except Exception:
        c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS invites(code TEXT PRIMARY KEY, note TEXT, created REAL, expires REAL, used_by TEXT, used_at REAL)")
    return c


def norm(code):
    return re.sub(r"[^A-Z0-9]", "", (code or "").upper())


def pretty(n):
    return n[:4] + "-" + n[4:]


def first_account():
    c = _con()
    try:
        return c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"] == 0
    except sqlite3.Error:
        return True          # users table not made yet: this is the very first account
    finally:
        c.close()


def check(code):
    """Sign-up allowed? (first account ever needs no code)"""
    if first_account():
        return True
    n = norm(code)
    if not n:
        return False
    c = _con()
    r = c.execute("SELECT * FROM invites WHERE code=?", (n,)).fetchone()
    c.close()
    return bool(r) and r["used_by"] is None and (not r["expires"] or r["expires"] > time.time())


def use(code, name):
    n = norm(code)
    if not n:
        return False
    c = _con()
    cur = c.execute("UPDATE invites SET used_by=?, used_at=? WHERE code=? AND used_by IS NULL", (name, time.time(), n))
    c.commit()
    ok = cur.rowcount == 1
    c.close()
    return ok


def create(note="", days=DAYS):
    c = _con()
    while True:
        n = "".join(secrets.choice(ALPHA) for _ in range(8))
        if not c.execute("SELECT 1 FROM invites WHERE code=?", (n,)).fetchone():
            break
    now = time.time()
    c.execute("INSERT INTO invites(code,note,created,expires) VALUES(?,?,?,?)", (n, note, now, now + days * 86400 if days else 0))
    c.commit(); c.close()
    return pretty(n)


def _main(a):
    if not a or a[0] not in ("new", "list", "revoke"):
        print(__doc__); return
    if a[0] == "new":
        note = a[1] if len(a) > 1 else ""
        days = int(a[2]) if len(a) > 2 and a[2].isdigit() else DAYS
        print("Invite code:", create(note, days), "| valid %d din | note: %s" % (days, note))
    elif a[0] == "list":
        c = _con()
        rows = c.execute("SELECT * FROM invites ORDER BY created DESC").fetchall()
        for r in rows:
            st = "USED by " + r["used_by"] if r["used_by"] else ("EXPIRED" if r["expires"] and r["expires"] < time.time() else "OPEN")
            print(pretty(r["code"]), "|", st, "|", r["note"] or "-")
        if not rows: print("Koi invite code nahi hai.")
    else:
        if len(a) < 2:
            print("Use: python invite.py revoke ABCD-EFGH"); return
        c = _con(); cur = c.execute("DELETE FROM invites WHERE code=? AND used_by IS NULL", (norm(a[1]),)); c.commit()
        print("Cancel ho gaya." if cur.rowcount else "Ye code nahi mila ya pehle hi use ho chuka hai.")


if __name__ == "__main__":
    _main(sys.argv[1:])
