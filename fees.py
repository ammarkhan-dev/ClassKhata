import re, sqlite3, calendar
from datetime import date
from urllib.parse import quote
from flask import render_template, request, redirect, session

MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"],
    "hi": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई",
           "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
}
WEEK = {"en": ["S", "M", "T", "W", "T", "F", "S"],
        "hi": ["र", "सो", "मं", "बु", "गु", "शु", "श"]}

MSG = {
    "en": ("Dear {parent},\n\nThis is a gentle reminder from {inst}. The fee of ₹{amt} "
           "for {name} (Class {cls}) for {mon} is pending, with the due date {due}.\n\n"
           "Kindly arrange the payment at your earliest convenience. If you have already "
           "paid, please ignore this message.\n\nThank you,\n{inst}"),
    "hi": ("आदरणीय {parent} जी,\n\n{inst} की ओर से सादर सूचना है कि {name} (कक्षा {cls}) "
           "की {mon} माह की ₹{amt} फ़ीस बकाया है। देय तिथि: {due}।\n\n"
           "कृपया शीघ्र भुगतान करने की कृपा करें। यदि आप भुगतान कर चुके हैं, "
           "तो कृपया इस संदेश को अनदेखा करें।\n\nधन्यवाद,\n{inst}"),
}

def fmt(d, lang):
    return f"{d.day} {MONTHS[lang][d.month - 1]} {d.year}"

def institute(lang):
    try:
        n = open("institute.txt", encoding="utf-8").read().strip()
        if n:
            return n
    except OSError:
        pass
    return "Our Institute" if lang == "en" else "हमारा संस्थान"

def parse_d(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None

def eligible(adm, y, m):
    a = parse_d(adm)
    return a is None or (y, m) >= (a.year, a.month)

def due_date(adm, y, m):
    a = parse_d(adm)
    day = a.day if a else 1
    return date(y, m, min(day, calendar.monthrange(y, m)[1]))

def wa_link(r, baaki, dd, y, m, lang):
    ph = "".join(ch for ch in (r["parent_phone"] or "") if ch.isdigit())
    if len(ph) != 10:
        return ""
    parent = r["parent_name"] or ("Parent/Guardian" if lang == "en" else "अभिभावक")
    msg = MSG[lang].format(parent=parent, inst=institute(lang), amt=baaki, name=r["name"],
                           cls=r["cls"], mon=f"{MONTHS[lang][m - 1]} {y}", due=fmt(dd, lang))
    return "https://wa.me/91" + ph + "?text=" + quote(msg)

def setup(app, db):
    with sqlite3.connect("classkhata.db") as c:
        c.execute("""CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER, month TEXT, amount INTEGER, paid_on TEXT)""")

    def month_arg(val):
        if val and re.fullmatch(r"\d{4}-\d{2}", val):
            y, m = int(val[:4]), int(val[5:])
            if 1 <= m <= 12 and 2000 <= y <= 2100:
                return y, m
        t = date.today()
        return t.year, t.month

    @app.route("/fees")
    def fees():
        lang = session.get("lang", "en")
        if lang not in MONTHS:
            lang = "en"
        today = date.today()
        y, m = month_arg(request.args.get("month"))
        mk = f"{y:04d}-{m:02d}"
        rows = db().execute("""SELECT s.*,
            COALESCE((SELECT SUM(amount) FROM payments p WHERE p.student_id=s.id AND p.month=?), 0) AS paid,
            (SELECT MAX(paid_on) FROM payments p WHERE p.student_id=s.id AND p.month=?) AS paid_on
            FROM students s WHERE s.monthly_fee > 0
            ORDER BY s.cls, s.name COLLATE NOCASE""", (mk, mk)).fetchall()
        due, done, soon = [], [], []
        received = pending = 0
        marks = {}
        by_cls = {c: [0, 0] for c in (9, 10, 11, 12)}
        for r in rows:
            if not eligible(r["admission_date"], y, m):
                continue
            dd = due_date(r["admission_date"], y, m)
            baaki = max(r["monthly_fee"] - r["paid"], 0)
            received += r["paid"]
            po = parse_d(r["paid_on"])
            it = dict(id=r["id"], name=r["name"], cls=r["cls"], fee=r["monthly_fee"],
                      baaki=baaki, due_s=fmt(dd, lang), late=(today - dd).days,
                      paid_on=fmt(po, lang) if po else "")
            if baaki == 0:
                done.append(it)
                continue
            dot = marks.setdefault(dd.day, [0, dd <= today])
            dot[0] += 1
            if dd <= today:
                it["link"] = wa_link(r, baaki, dd, y, m, lang)
                due.append(it)
                pending += baaki
                if r["cls"] in by_cls:
                    by_cls[r["cls"]][0] += 1
                    by_cls[r["cls"]][1] += baaki
            else:
                soon.append(it)
        due.sort(key=lambda i: (-i["late"], i["cls"], i["name"].lower()))
        pv = (y - 1, 12) if m == 1 else (y, m - 1)
        nx = (y + 1, 1) if m == 12 else (y, m + 1)
        return render_template("fees.html", month=mk, month_label=f"{MONTHS[lang][m - 1]} {y}",
            weeks=calendar.Calendar(6).monthdayscalendar(y, m), marks=marks, wk=WEEK[lang],
            is_cur=(y == today.year and m == today.month), today=today,
            today_label=fmt(today, lang), prev=f"{pv[0]:04d}-{pv[1]:02d}",
            nxt=f"{nx[0]:04d}-{nx[1]:02d}", due=due, done=done, soon=soon,
            received=received, pending=pending, by_cls=by_cls)

    @app.route("/collect", methods=["POST"])
    def collect():
        y, m = month_arg(request.form.get("month"))
        mk = f"{y:04d}-{m:02d}"
        try:
            sid = int(request.form.get("sid", 0))
        except ValueError:
            sid = 0
        s = db().execute("SELECT monthly_fee FROM students WHERE id=?", (sid,)).fetchone()
        if s:
            paid = db().execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE student_id=? AND month=?",
                                (sid, mk)).fetchone()[0]
            left = s["monthly_fee"] - paid
            if left > 0:
                db().execute("INSERT INTO payments(student_id,month,amount,paid_on) VALUES(?,?,?,?)",
                             (sid, mk, left, date.today().isoformat()))
                db().commit()
        return redirect(f"/fees?month={mk}")

    @app.route("/undo", methods=["POST"])
    def undo():
        y, m = month_arg(request.form.get("month"))
        mk = f"{y:04d}-{m:02d}"
        try:
            sid = int(request.form.get("sid", 0))
        except ValueError:
            sid = 0
        db().execute("DELETE FROM payments WHERE student_id=? AND month=?", (sid, mk))
        db().commit()
        return redirect(f"/fees?month={mk}")

def months_since(adm, today):
    a = parse_d(adm) or today.replace(day=1)
    y, m = a.year, a.month
    while (y, m) <= (today.year, today.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)

def fee_history(adm, fee, paid_by_month, today):
    out = []
    for y, m in months_since(adm, today):
        key = f"{y:04d}-{m:02d}"
        dd = due_date(adm, y, m)
        paid = paid_by_month.get(key, 0)
        baaki = max(fee - paid, 0)
        st = "paid" if baaki == 0 else ("due" if dd <= today else "soon")
        out.append(dict(y=y, m=m, key=key, due=dd, paid=paid, baaki=baaki, st=st))
    return out

def pending_all(db):
    today = date.today()
    n = amt = 0
    for s in db().execute("SELECT id, admission_date, monthly_fee FROM students WHERE monthly_fee > 0").fetchall():
        pm = {r["month"]: r["amt"] for r in db().execute(
            "SELECT month, SUM(amount) amt FROM payments WHERE student_id=? GROUP BY month", (s["id"],))}
        hist = fee_history(s["admission_date"], s["monthly_fee"], pm, today)
        owed = sum(h["baaki"] for h in hist if h["st"] == "due")
        if owed:
            n += 1
            amt += owed
    return n, amt

def months_since(adm, today):
    a = parse_d(adm) or today.replace(day=1)
    y, m = a.year, a.month
    while (y, m) <= (today.year, today.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)

def fee_history(adm, fee, paid_by_month, today):
    out = []
    for y, m in months_since(adm, today):
        key = f"{y:04d}-{m:02d}"
        dd = due_date(adm, y, m)
        paid = paid_by_month.get(key, 0)
        baaki = max(fee - paid, 0)
        st = "paid" if baaki == 0 else ("due" if dd <= today else "soon")
        out.append(dict(y=y, m=m, key=key, due=dd, paid=paid, baaki=baaki, st=st))
    return out

def pending_all(db):
    today = date.today()
    n = amt = 0
    for s in db().execute("SELECT id, admission_date, monthly_fee FROM students WHERE monthly_fee > 0").fetchall():
        pm = {r["month"]: r["amt"] for r in db().execute(
            "SELECT month, SUM(amount) amt FROM payments WHERE student_id=? GROUP BY month", (s["id"],))}
        hist = fee_history(s["admission_date"], s["monthly_fee"], pm, today)
        owed = sum(h["baaki"] for h in hist if h["st"] == "due")
        if owed:
            n += 1
            amt += owed
    return n, amt

# ---- professional reminder message (uses institute name and your name) ----
import store

MSG = {
    "en": ("Dear {parent},\n\nGreetings from {inst}.\n\n"
           "This is a gentle reminder that the monthly fee for {name} (Class {cls}) "
           "for {mon} is pending.\n\nFee amount: ₹{amt}\nDue date: {due}\n\n"
           "Kindly arrange the payment at your earliest convenience. If you have already "
           "paid, please disregard this message.\n\nThank you for your continued support.\n\n"
           "Warm regards,\n{sign}"),
    "hi": ("आदरणीय {parent} जी,\n\n{inst} की ओर से नमस्कार।\n\n"
           "सादर सूचित किया जाता है कि {name} (कक्षा {cls}) की {mon} माह की फ़ीस बकाया है।\n\n"
           "फ़ीस राशि: ₹{amt}\nदेय तिथि: {due}\n\n"
           "कृपया सुविधानुसार शीघ्र भुगतान करने की कृपा करें। यदि आप पहले ही भुगतान कर चुके हैं, "
           "तो कृपया इस संदेश को अनदेखा करें।\n\nआपके सहयोग के लिए धन्यवाद।\n\n"
           "सादर,\n{sign}"),
}

def institute(lang):
    return store.get("institute") or ("Our Institute" if lang == "en" else "हमारा संस्थान")

def wa_link(r, baaki, dd, y, m, lang):
    ph = "".join(ch for ch in (r["parent_phone"] or "") if ch.isdigit())
    if len(ph) != 10:
        return ""
    inst = institute(lang)
    sign = "\n".join(dict.fromkeys(x for x in (session.get("name", ""), inst) if x))
    parent = r["parent_name"] or ("Parent/Guardian" if lang == "en" else "अभिभावक")
    msg = MSG[lang].format(parent=parent, inst=inst, amt=f"{baaki:,}", name=r["name"],
                           cls=r["cls"], mon=f"{MONTHS[lang][m - 1]} {y}", due=fmt(dd, lang), sign=sign)
    return "https://wa.me/91" + ph + "?text=" + quote(msg)

def owed_map(db):
    today = date.today()
    out = {}
    for s in db().execute("SELECT id, admission_date, monthly_fee FROM students WHERE monthly_fee > 0").fetchall():
        pm = {r["month"]: r["amt"] for r in db().execute(
            "SELECT month, SUM(amount) amt FROM payments WHERE student_id=? GROUP BY month", (s["id"],))}
        hist = fee_history(s["admission_date"], s["monthly_fee"], pm, today)
        out[s["id"]] = sum(h["baaki"] for h in hist if h["st"] == "due")
    return out

def fee_state(db):
    today = date.today()
    out = {}
    for s in db().execute("SELECT id, admission_date, monthly_fee FROM students WHERE monthly_fee > 0").fetchall():
        pm = {r["month"]: r["amt"] for r in db().execute(
            "SELECT month, SUM(amount) amt FROM payments WHERE student_id=? GROUP BY month", (s["id"],))}
        hist = fee_history(s["admission_date"], s["monthly_fee"], pm, today)
        owed = sum(h["baaki"] for h in hist if h["st"] == "due")
        if owed:
            st = "pending"
        elif any(h["st"] == "soon" for h in hist):
            st = "upcoming"
        else:
            st = "paid"
        out[s["id"]] = (owed, st)
    return out
