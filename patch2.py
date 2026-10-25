import os, re, shutil

LOG = []

def say(ok, msg):
    LOG.append(("OK   " if ok else "SKIP ") + msg)

def read(p):
    return open(p, encoding="utf-8").read()

def write(p, s):
    shutil.copy2(p, p + ".bak")
    open(p, "w", encoding="utf-8").write(s)

OV_BLOCK = '''

# ---- per-month overrides (amount / due date) ----
from flask import g

def ov_get(sid, key):
    try:
        return (g.get("ov") or {}).get((sid, key))
    except RuntimeError:
        return None

def months_since(adm, today):
    a = parse_d(adm) or today.replace(day=1)
    y, m = a.year, a.month
    while (y, m) <= (today.year, today.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)

def fee_history(adm, fee, paid_by_month, today, sid=None):
    out = []
    for y, m in months_since(adm, today):
        key = f"{y:04d}-{m:02d}"
        ov = ov_get(sid, key)
        dd = (parse_d(ov[1]) if ov and ov[1] else None) or due_date(adm, y, m)
        paid = paid_by_month.get(key, 0)
        amt = ov[0] if ov and ov[0] is not None else fee
        baaki = max(amt - paid, 0)
        st = "paid" if baaki == 0 else ("due" if dd <= today else "soon")
        out.append(dict(y=y, m=m, key=key, due=dd, paid=paid, baaki=baaki, amt=amt, st=st))
    return out

def _pay_all(db):
    pay = {}
    for p in db().execute("SELECT student_id sid, month, SUM(amount) amt FROM payments GROUP BY student_id, month"):
        pay.setdefault(p["sid"], {})[p["month"]] = p["amt"]
    return pay

def pending_all(db):
    today = date.today()
    pay = _pay_all(db)
    n = amt = 0
    for s in db().execute("SELECT id, admission_date, monthly_fee FROM students WHERE monthly_fee > 0").fetchall():
        hist = fee_history(s["admission_date"], s["monthly_fee"], pay.get(s["id"], {}), today, sid=s["id"])
        owed = sum(h["baaki"] for h in hist if h["st"] == "due")
        if owed:
            n += 1
            amt += owed
    return n, amt

def owed_map(db):
    today = date.today()
    pay = _pay_all(db)
    out = {}
    for s in db().execute("SELECT id, admission_date, monthly_fee FROM students WHERE monthly_fee > 0").fetchall():
        hist = fee_history(s["admission_date"], s["monthly_fee"], pay.get(s["id"], {}), today, sid=s["id"])
        out[s["id"]] = sum(h["baaki"] for h in hist if h["st"] == "due")
    return out

def fee_state(db):
    today = date.today()
    pay = _pay_all(db)
    out = {}
    for s in db().execute("SELECT id, admission_date, monthly_fee FROM students").fetchall():
        fee = s["monthly_fee"] or 0
        if fee <= 0:
            out[s["id"]] = (0, "none")
            continue
        hist = fee_history(s["admission_date"], fee, pay.get(s["id"], {}), today, sid=s["id"])
        owed = sum(h["baaki"] for h in hist if h["st"] == "due")
        if owed:
            out[s["id"]] = (owed, "pending")
        elif not hist or any(h["st"] == "soon" for h in hist):
            out[s["id"]] = (0, "upcoming")
        else:
            out[s["id"]] = (0, "paid")
    return out
'''

# ---------- fees.py ----------
s = read("fees.py")
if "def ov_get(" in s:
    say(True, "fees.py: overrides pehle se hain")
else:
    s += OV_BLOCK
    say(True, "fees.py: ov_get, fee_history, pending_all, owed_map, fee_state dobara likhe (file ke end me)")
pdd = re.compile(r'^([ \t]*)dd = due_date\(r\["admission_date"\], y, m\)[ \t]*$', re.M)
pbk = re.compile(r'^([ \t]*)baaki = max\(r\["monthly_fee"\] - r\["paid"\], 0\)[ \t]*$', re.M)
if 'ov_get(r["id"]' in s:
    say(True, "fees.py: Fees tab pehle se patched")
elif pdd.search(s) and pbk.search(s):
    s = pdd.sub(lambda m: m.group(1) + 'ov = ov_get(r["id"], f"{y:04d}-{m:02d}")\n' + m.group(1) + 'dd = (parse_d(ov[1]) if ov and ov[1] else None) or due_date(r["admission_date"], y, m)', s, count=1)
    s = pbk.sub(lambda m: m.group(1) + 'baaki = max((ov[0] if ov and ov[0] is not None else r["monthly_fee"]) - r["paid"], 0)', s, count=1)
    say(True, "fees.py: Fees tab ab amount/due date ka badlav maanta hai")
else:
    say(False, "fees.py: Fees tab ka hisaab wala hissa nahi mila (Fees tab me amount edit nahi dikhega)")
pcol = re.compile(r'^([ \t]*)@app\.route\("/collect", methods=\["POST"\]\)[ \t]*\n[ \t]*def collect\(\):', re.M)
if "def _old_collect" in s:
    ok_col = True
elif pcol.search(s):
    s = pcol.sub(lambda m: m.group(1) + "def _old_collect():", s, count=1)
    ok_col = True
else:
    ok_col = False
say(ok_col, "fees.py: purana /collect route hata diya" if ok_col else "fees.py: purana /collect route nahi mila")
write("fees.py", s)

# ---------- students.py ----------
s = read("students.py")
pdet = re.compile(r'^([ \t]*)@app\.route\("/students/<int:sid>"\)[ \t]*\n[ \t]*def student_detail\(sid\):', re.M)
if "def _old_detail" in s:
    ok_det = True
elif pdet.search(s):
    s = pdet.sub(lambda m: m.group(1) + "def _old_detail(sid):", s, count=1)
    ok_det = True
else:
    ok_det = False
say(ok_det, "students.py: purana profile route hata diya" if ok_det else "students.py: purana profile route nahi mila")
old = 'for tbl in ("attendance", "payments", "student_batches"):'
if old in s:
    s = s.replace(old, 'for tbl in ("attendance", "payments", "student_batches", "entry_ov", "entry_log"):', 1)
write("students.py", s)

# ---------- records.py / report.py ----------
for f, pat, new, mark in (
    ("records.py", r'fee_history\((r\["admission_date"\], fee, pm, upto)\)', r'fee_history(\1, sid=sid)', "upto, sid=sid)"),
    ("report.py", r'fee_history\((r\["admission_date"\], fee, mine, today)\)', r'fee_history(\1, sid=r["id"])', 'today, sid=r["id"])'),
):
    if not os.path.exists(f):
        say(False, f + ": file nahi mili")
        continue
    s = read(f)
    if mark in s:
        say(True, f + ": pehle se patched")
    elif re.search(pat, s):
        write(f, re.sub(pat, new, s, count=1))
        say(True, f + ": override lagaya")
    else:
        say(False, f + ": fee_history wali line nahi mili (zaroori nahi)")

# ---------- app.py ----------
for need in ("entry.py", "templates/profile.html", "templates/entry.html"):
    if not os.path.exists(need):
        say(False, need + ": file nahi hai (pichhle steps adhoore?)")
s = read("app.py")
if "entry.setup(app, db)" in s:
    say(True, "app.py: entry pehle se juda hai")
elif ok_col and ok_det and os.path.exists("entry.py"):
    mi = re.search(r"^import i18n, auth[^\n]*$", s, re.M)
    mm = re.search(r'^if __name__ == "__main__":', s, re.M)
    if mi and mm:
        line = mi.group(0)
        if not re.search(r"\bentry\b", line):
            s = s.replace(line, line + ", entry", 1)
        s = re.sub(r'^if __name__ == "__main__":', "entry.setup(app, db)\n\nif __name__ == \"__main__\":", s, count=1, flags=re.M)
        write("app.py", s)
        say(True, "app.py: entry juda")
    else:
        say(False, "app.py: import ya main wali line nahi mili, entry nahi juda")
else:
    say(False, "app.py: entry nahi juda (upar ke SKIP dekh)")

# ---------- base.html ----------
s = read("templates/base.html")
if "{% block header %}" in s:
    say(True, "base.html: header block pehle se hai")
elif "<header>" in s and "</header>" in s:
    s = s.replace("<header>", "{% block header %}<header>", 1).replace("</header>", "</header>{% endblock %}", 1)
    say(True, "base.html: header block bana")
else:
    say(False, "base.html: <header> nahi mila")
if "{% block nav %}" in s:
    say(True, "base.html: nav block pehle se hai")
elif "{% if user_name %}<nav>" in s and "</nav>{% endif %}" in s:
    s = s.replace("{% if user_name %}<nav>", "{% block nav %}{% if user_name %}<nav>", 1).replace("</nav>{% endif %}", "</nav>{% endif %}{% endblock %}", 1)
    say(True, "base.html: nav block bana")
else:
    say(False, "base.html: nav wali line nahi mili")
write("templates/base.html", s)

# ---------- .gitignore ----------
gi = read(".gitignore") if os.path.exists(".gitignore") else ""
add = [x for x in ("*.bak", "classkhata-report.txt", "audit.py", "patch2.py") if x not in gi.split()]
if add:
    open(".gitignore", "a").write(("" if (gi.endswith("\n") or not gi) else "\n") + "\n".join(add) + "\n")

print("\n".join(LOG))
print("--- SKIP wali lines mujhe bhej dena. Purani files .bak naam se bachi hain.")
