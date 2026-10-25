import re, sqlite3
from datetime import date, datetime
from flask import render_template, request, redirect, abort, session, g
from fees import MONTHS, parse_d, due_date, eligible, wa_link, months_since
from batches import t12

def lang_now():
    l = session.get("lang", "en")
    return l if l in MONTHS else "en"

def mname(lang, m, short=False):
    n = MONTHS[lang][m - 1]
    return n[:3] if short and lang == "en" else n

def sd(d, lang):
    return f"{d.day} {mname(lang, d.month, True)} {d.year}"

def sdm(d, lang):
    return f"{d.day} {mname(lang, d.month, True)}"

def nxt(y, m):
    return (y + 1, 1) if m == 12 else (y, m + 1)

def entry_target(db, sid, month):
    s = db().execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    if not s or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        abort(404)
    y, m = int(month[:4]), int(month[5:])
    t = date.today()
    if not eligible(s["admission_date"], y, m) or (y, m) > nxt(t.year, t.month):
        abort(404)
    return s, y, m

def entry_info(db, s, y, m):
    mk = f"{y:04d}-{m:02d}"
    ov = db().execute("SELECT amount, due_date FROM entry_ov WHERE student_id=? AND month=?", (s["id"], mk)).fetchone()
    amt = ov["amount"] if ov and ov["amount"] is not None else (s["monthly_fee"] or 0)
    dd = (parse_d(ov["due_date"]) if ov and ov["due_date"] else None) or due_date(s["admission_date"], y, m)
    p = db().execute("SELECT COALESCE(SUM(amount),0) a, MAX(paid_on) d, MAX(id) pid FROM payments WHERE student_id=? AND month=?",
                     (s["id"], mk)).fetchone()
    baaki = max(amt - p["a"], 0)
    st = "paid" if baaki == 0 else ("due" if dd <= date.today() else "soon")
    mode = None
    if p["pid"]:
        mode = db().execute("SELECT COALESCE(mode,'Cash') FROM payments WHERE id=?", (p["pid"],)).fetchone()[0]
    return dict(key=mk, y=y, m=m, amt=amt, due=dd, paid=p["a"], paid_on=p["d"], pid=p["pid"],
                mode=mode, baaki=baaki, st=st)

def log(db, sid, mk, code, a="", b=""):
    db().execute("INSERT INTO entry_log(student_id,month,at,code,a,b) VALUES(?,?,?,?,?,?)",
                 (sid, mk, datetime.now().strftime("%Y-%m-%d %H:%M"), code, str(a), str(b)))

def record_payment(db, s, mk, mode):
    e = entry_info(db, s, int(mk[:4]), int(mk[5:]))
    if e["baaki"] <= 0:
        return
    db().execute("INSERT INTO payments(student_id,month,amount,paid_on,mode) VALUES(?,?,?,?,?)",
                 (s["id"], mk, e["baaki"], date.today().isoformat(), mode))
    db().execute("INSERT OR REPLACE INTO entry_ov(student_id,month,amount,due_date) VALUES(?,?,?,?)",
                 (s["id"], mk, e["amt"], e["due"].isoformat()))
    log(db, s["id"], mk, "paid", e["baaki"], mode)
    db().commit()

def setup(app, db):
    with sqlite3.connect("classkhata.db") as c:
        c.execute("CREATE TABLE IF NOT EXISTS entry_ov(student_id INTEGER, month TEXT, amount INTEGER, due_date TEXT, PRIMARY KEY(student_id, month))")
        c.execute("CREATE TABLE IF NOT EXISTS entry_log(id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, month TEXT, at TEXT, code TEXT, a TEXT, b TEXT)")
        if "mode" not in [r[1] for r in c.execute("PRAGMA table_info(payments)")]:
            c.execute("ALTER TABLE payments ADD COLUMN mode TEXT DEFAULT 'Cash'")

    @app.before_request
    def load_ov():
        if request.endpoint == "static":
            return
        g.ov = {(r["student_id"], r["month"]): (r["amount"], r["due_date"])
                for r in db().execute("SELECT student_id, month, amount, due_date FROM entry_ov")}

    @app.route("/students/<int:sid>")
    def student_detail(sid):
        s = db().execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not s:
            abort(404)
        lang = lang_now()
        today = date.today()
        ny, nm = nxt(today.year, today.month)
        pm = {r["month"]: r["amt"] for r in db().execute(
            "SELECT month, SUM(amount) amt FROM payments WHERE student_id=? GROUP BY month", (sid,))}
        entries = []
        if (s["monthly_fee"] or 0) > 0:
            adm = s["admission_date"] or today.replace(day=1).isoformat()
            for y, m in months_since(adm, date(ny, nm, 1)):
                e = entry_info(db, s, y, m)
                y2, m2 = nxt(y, m)
                e["label"] = f"{mname(lang, m)} {y}"
                e["range"] = f"{sdm(e['due'], lang)} – {sdm(due_date(s['admission_date'], y2, m2), lang)}"
                entries.append(e)
            entries.reverse()
        due_list = [e for e in entries if e["st"] == "due"]
        wa = ""
        if due_list:
            o = due_list[-1]
            wa = wa_link(s, o["baaki"], o["due"], o["y"], o["m"], lang)
        a0 = s["admission_date"] or "0000-00-00"
        r = db().execute("""SELECT
            (SELECT COUNT(*) FROM attendance x WHERE x.student_id=? AND x.status='P' AND x.day>=?) AS pres,
            (SELECT COUNT(DISTINCT y.day) FROM attendance y JOIN students t ON t.id=y.student_id
             WHERE t.cls=? AND y.day>=?) AS tot""", (sid, a0, s["cls"], a0)).fetchone()
        ex = db().execute("SELECT * FROM student_extra WHERE student_id=?", (sid,)).fetchone()
        blist = [b["name"] for b in db().execute(
            "SELECT b.name FROM student_batches sb JOIN batches b ON b.id=sb.batch_id WHERE sb.student_id=? ORDER BY b.name", (sid,))]
        return render_template("profile.html", s=s, ex=ex, blist=blist, entries=entries, wa=wa,
            pend=sum(e["baaki"] for e in entries if e["st"] == "due"),
            upc=sum(e["baaki"] for e in entries if e["st"] == "soon"), coll=sum(pm.values()),
            pct=round(100 * r["pres"] / r["tot"]) if r["tot"] else None)

    @app.route("/students/<int:sid>/entry/<month>")
    def entry_page(sid, month):
        s, y, m = entry_target(db, sid, month)
        lang = lang_now()
        e = entry_info(db, s, y, m)
        logs = []
        for r in db().execute("SELECT at, code, a, b FROM entry_log WHERE student_id=? AND month=? ORDER BY id DESC", (sid, month)):
            a, b = r["a"], r["b"]
            if r["code"] == "due":
                a, b = sd(date.fromisoformat(a), lang), sd(date.fromisoformat(b), lang)
            w = datetime.strptime(r["at"], "%Y-%m-%d %H:%M")
            logs.append(dict(when=f"{sd(w.date(), lang)}, {t12(w.strftime('%H:%M'))}", code=r["code"], a=a, b=b))
        wa = wa_link(s, e["baaki"], e["due"], y, m, lang) if e["baaki"] > 0 else ""
        return render_template("entry.html", s=s, e=e, due_s=sd(e["due"], lang), logs=logs, wa=wa,
            label=f"{mname(lang, m)} {y}", err=request.args.get("err"),
            paid_s=sd(date.fromisoformat(e["paid_on"]), lang) if e["paid_on"] else "")

    @app.route("/students/<int:sid>/entry/<month>/save", methods=["POST"])
    def entry_save(sid, month):
        s, y, m = entry_target(db, sid, month)
        e = entry_info(db, s, y, m)
        due = parse_d(request.form.get("due", ""))
        try:
            amt = int(request.form.get("amount", ""))
        except ValueError:
            amt = -1
        if amt < 0 or amt > 1000000 or not due:
            return redirect(f"/students/{sid}/entry/{month}?err=1")
        if amt != e["amt"]:
            log(db, sid, month, "amt", e["amt"], amt)
        if due != e["due"]:
            log(db, sid, month, "due", e["due"].isoformat(), due.isoformat())
        db().execute("INSERT OR REPLACE INTO entry_ov(student_id,month,amount,due_date) VALUES(?,?,?,?)",
                     (sid, month, amt, due.isoformat()))
        db().commit()
        return redirect(f"/students/{sid}/entry/{month}")

    @app.route("/students/<int:sid>/entry/<month>/pay", methods=["POST"])
    def entry_pay(sid, month):
        s, y, m = entry_target(db, sid, month)
        mode = request.form.get("mode", "Cash")
        record_payment(db, s, month, mode if mode in ("Cash", "UPI", "Other") else "Cash")
        return redirect(f"/students/{sid}/entry/{month}")

    @app.route("/students/<int:sid>/entry/<month>/undo", methods=["POST"])
    def entry_undo(sid, month):
        entry_target(db, sid, month)
        db().execute("DELETE FROM payments WHERE student_id=? AND month=?", (sid, month))
        log(db, sid, month, "undo")
        db().commit()
        return redirect(f"/students/{sid}/entry/{month}")

    @app.route("/collect", methods=["POST"])
    def collect():
        month = request.form.get("month", "")
        try:
            sid = int(request.form.get("sid", 0))
        except ValueError:
            abort(400)
        s, y, m = entry_target(db, sid, month)
        record_payment(db, s, month, "Cash")
        return redirect(f"/fees?month={month}")

    @app.route("/receipt/<int:pid>")
    def receipt(pid):
        p = db().execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone()
        if not p:
            abort(404)
        st = db().execute("""SELECT name, cls, parent_name, acad_session FROM students WHERE id=?
            UNION ALL SELECT name, cls, parent_name, acad_session FROM records WHERE id=?""",
            (p["student_id"], p["student_id"])).fetchone()
        if not st:
            abort(404)
        lang = lang_now()
        y, m = int(p["month"][:4]), int(p["month"][5:])
        return render_template("receipt.html", p=p, st=st, no=f"{pid:05d}", mon=f"{mname(lang, m)} {y}",
                               on=sd(date.fromisoformat(p["paid_on"]), lang))
