import sqlite3
from datetime import date
from urllib.parse import urlencode
from flask import render_template, request, redirect, abort, session
from fees import fee_history, fmt, MONTHS, owed_map, fee_state, fee_history_s, fee_plan, sched
from batches import days_text, time_text

def cur_session():
    t = date.today()
    y = t.year if t.month >= 4 else t.year - 1
    return f"{y}-{(y + 1) % 100:02d}"

def session_options(extra=None):
    y = int(cur_session()[:4])
    opts = [f"{k}-{(k + 1) % 100:02d}" for k in (y - 1, y, y + 1)]
    if extra and extra not in opts:
        opts.append(extra)
    return opts

def default_end(ses):
    return f"{int(ses[:4]) + 1}-03-31"

def digits10(s):
    d = "".join(ch for ch in s if ch.isdigit())
    if len(d) > 10 and d.startswith("91"):
        d = d[-10:]
    return d if len(d) == 10 else None

def to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

def parse(form):
    name = form.get("name", "").strip()
    if not name:
        return None, "err_student_name"
    phone = digits10(form.get("phone", ""))
    if not phone:
        return None, "err_phone"
    try:
        fee = int(form.get("fee", ""))
    except ValueError:
        fee = -1
    if fee < 0:
        return None, "err_fee"
    try:
        adm = date.fromisoformat(form.get("adm", "")).isoformat()
        end = date.fromisoformat(form.get("end", "")).isoformat()
    except ValueError:
        return None, "err_date"
    if end <= adm:
        return None, "err_end"
    cls = to_int(form.get("cls"))
    if cls not in (9, 10, 11, 12):
        return None, "err_student_name"
    ses = form.get("ses", "").strip() or cur_session()
    return (name, cls, form.get("parent_name", "").strip(), phone, fee, adm, ses, end), None

def next_roll(db):
    m = db().execute("SELECT MAX(CAST(roll AS INTEGER)) FROM student_extra").fetchone()[0] or 0
    return f"{m + 1:04d}"

def save_extra(db, sid, form):
    g = form.get("gender", "")
    roll = form.get("roll", "").strip()[:12] or next_roll(db)
    db().execute("INSERT OR REPLACE INTO student_extra(student_id,roll,gender,address) VALUES(?,?,?,?)",
                 (sid, roll, g if g in ("Male", "Female", "Other") else "", form.get("address", "").strip()[:200]))
    db().execute("DELETE FROM student_batches WHERE student_id=?", (sid,))
    for b in form.getlist("batch"):
        if b.isdigit():
            db().execute("INSERT OR IGNORE INTO student_batches VALUES(?,?)", (sid, int(b)))
    ft, bs = fee_plan(form)
    db().execute("INSERT OR REPLACE INTO student_fee(student_id,bill_start,fee_type) VALUES(?,?,?)", (sid, bs, ft))
    db().commit()

def form_page(db, s, err, action, title_key):
    bl = [dict(id=r["id"], name=r["name"], days_s=days_text(r["days"]), time_s=time_text(r["t_from"], r["t_to"]))
          for r in db().execute("SELECT * FROM batches ORDER BY name COLLATE NOCASE")]
    sel = [int(b) for b in s.get("batch_ids", []) if str(b).isdigit()]
    if "bday" not in s:
        r = db().execute("SELECT bill_start FROM student_fee WHERE student_id=?", (s.get("id", 0),)).fetchone()
        s["bday"] = int(r["bill_start"][8:10]) if r and r["bill_start"] else ""
    return render_template("student_form.html", s=s, err=err, action=action, title_key=title_key,
                           sessions=session_options(s.get("acad_session")), batches=bl, sel=sel)

def setup(app, db):
    with sqlite3.connect("classkhata.db") as c:
        c.execute("""CREATE TABLE IF NOT EXISTS students(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, cls INTEGER NOT NULL,
            parent_phone TEXT, monthly_fee INTEGER DEFAULT 0)""")
        have = [r[1] for r in c.execute("PRAGMA table_info(students)")]
        for col in ("parent_name", "admission_date", "acad_session", "session_end"):
            if col not in have:
                c.execute(f"ALTER TABLE students ADD COLUMN {col} TEXT")

    def get_student(sid):
        s = db().execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not s:
            abort(404)
        return s

    def keep(s):
        f = request.form
        s.update(name=f.get("name", ""), cls=f.get("cls", "9"), parent_name=f.get("parent_name", ""),
                 parent_phone=f.get("phone", ""), monthly_fee=f.get("fee", ""),
                 admission_date=f.get("adm", ""), acad_session=f.get("ses", ""),
                 session_end=f.get("end", ""), roll=f.get("roll", ""), gender=f.get("gender", ""),
                 address=f.get("address", ""), batch_ids=f.getlist("batch"),
                 bday=f.get("bday", ""))
        return s

    NEW = "INSERT INTO students(name,cls,parent_name,parent_phone,monthly_fee,admission_date,acad_session,session_end) VALUES(?,?,?,?,?,?,?,?)"
    UPD = "UPDATE students SET name=?,cls=?,parent_name=?,parent_phone=?,monthly_fee=?,admission_date=?,acad_session=?,session_end=? WHERE id=?"

    def fetch(table, q, cls, bid):
        sql = (f"SELECT t.id, t.name, t.cls, t.parent_phone, t.acad_session, x.roll FROM {table} t "
               "LEFT JOIN student_extra x ON x.student_id=t.id WHERE 1=1")
        args = []
        if q:
            like = "%" + q.replace("%", "").replace("_", "") + "%"
            sql += " AND (t.name LIKE ? OR x.roll LIKE ? OR t.parent_phone LIKE ?)"
            args += [like, like, like]
        if cls:
            sql += " AND t.cls=?"
            args.append(cls)
        if bid:
            sql += " AND t.id IN (SELECT student_id FROM student_batches WHERE batch_id=?)"
            args.append(bid)
        return db().execute(sql + " ORDER BY t.name COLLATE NOCASE", args).fetchall()

    @app.route("/students")
    def students():
        stt = request.args.get("status", "active")
        if stt not in ("active", "inactive", "all"):
            stt = "active"
        fee = request.args.get("fee", "")
        if fee not in ("paid", "pending", "upcoming"):
            fee = ""
        srt = request.args.get("sort", "name")
        if srt not in ("name", "recent", "due"):
            srt = "name"
        q = request.args.get("q", "").strip()[:40]
        cls = to_int(request.args.get("cls"))
        cls = cls if cls in (9, 10, 11, 12) else None
        bid = to_int(request.args.get("batch"))
        state = fee_state(db)

        def card(r, inactive):
            o, st = (0, "") if inactive else state.get(r["id"], (0, "paid"))
            return dict(id=r["id"], name=r["name"], phone=r["parent_phone"] or "", roll=r["roll"] or "",
                        ses=r["acad_session"] or "", inactive=inactive, owed=o, fst=st)

        rows = []
        if stt in ("active", "all"):
            rows += [card(r, False) for r in fetch("students", q, cls, bid)]
        if stt in ("inactive", "all"):
            rows += [card(r, True) for r in fetch("records", q, cls, bid)]
        if fee:
            rows = [c for c in rows if c["fst"] == fee]
        if srt == "recent":
            rows.sort(key=lambda c: c["id"], reverse=True)
        elif srt == "due":
            rows.sort(key=lambda c: (-c["owed"], c["name"].lower()))
        else:
            rows.sort(key=lambda c: c["name"].lower())
        bl = [dict(id=b["id"], name=b["name"]) for b in db().execute("SELECT id, name FROM batches ORDER BY name COLLATE NOCASE")]
        bname = next((b["name"] for b in bl if b["id"] == bid), "")
        nf = (stt != "active") + (fee != "") + (srt != "name")

        def href(**over):
            p = dict(status=stt, fee=fee, sort=srt, q=q, cls=cls or "", batch=bid or "")
            p.update(over)
            return "/students?" + urlencode({k: v for k, v in p.items() if v not in ("", None)})

        return render_template("students.html", rows=rows, status=stt, fee=fee, sort=srt, q=q,
                               cls=cls, bid=bid, nf=nf, batches=bl, bname=bname, href=href)

    @app.route("/students/class/<int:cls>")
    def students_class(cls):
        return redirect(f"/students?cls={cls}")

    @app.route("/students/<int:sid>")
    def student_detail(sid):
        s = get_student(sid)
        lang = session.get("lang", "en")
        if lang not in MONTHS:
            lang = "en"
        today = date.today()
        fee = s["monthly_fee"] or 0
        pm = {r["month"]: r["amt"] for r in db().execute(
            "SELECT month, SUM(amount) amt FROM payments WHERE student_id=? GROUP BY month", (sid,))}
        hist = fee_history_s(db, sid, s["admission_date"], fee, pm, today) if fee > 0 else []
        for h in hist:
            nm = MONTHS[lang][h["m"] - 1]
            h["label"] = (nm[:3] if lang == "en" else nm) + " " + str(h["y"])[2:]
            h["due_s"] = fmt(h["due"], lang)
            h["late"] = (today - h["due"]).days
        counted = [h for h in hist if h["st"] != "soon"]
        info = dict(cur=hist[-1] if hist else None,
                    paid_n=sum(1 for h in counted if h["st"] == "paid"), tot_n=len(counted),
                    total_paid=sum(pm.values()),
                    pending=sum(h["baaki"] for h in hist if h["st"] == "due"))
        adm = s["admission_date"] or "0000-00-00"
        r = db().execute("""SELECT
            (SELECT COUNT(*) FROM attendance x WHERE x.student_id=? AND x.status='P' AND x.day>=?) AS pres,
            (SELECT COUNT(DISTINCT y.day) FROM attendance y JOIN students t ON t.id=y.student_id
             WHERE t.cls=? AND y.day>=?) AS tot""", (sid, adm, s["cls"], adm)).fetchone()
        pct = round(100 * r["pres"] / r["tot"]) if r["tot"] else None
        ex = db().execute("SELECT * FROM student_extra WHERE student_id=?", (sid,)).fetchone()
        blist = [b["name"] for b in db().execute(
            "SELECT b.name FROM student_batches sb JOIN batches b ON b.id=sb.batch_id WHERE sb.student_id=? ORDER BY b.name", (sid,))]
        return render_template("student_detail.html", s=s, hist=hist, info=info, att=r, pct=pct, ex=ex, blist=blist,
                               sch=sched(db, sid, s["admission_date"]))

    @app.route("/students/add", methods=["GET", "POST"])
    def student_add():
        s = dict(name="", cls=9, parent_name="", parent_phone="", monthly_fee="",
                 admission_date=date.today().isoformat(), acad_session=cur_session(),
                 session_end=default_end(cur_session()), roll=next_roll(db), gender="", address="", batch_ids=[])
        err = None
        if request.method == "POST":
            v, err = parse(request.form)
            if not err:
                cur = db().execute(NEW, v)
                db().commit()
                save_extra(db, cur.lastrowid, request.form)
                return redirect("/students")
            s = keep(s)
        return form_page(db, s, err, "/students/add", "add_student_title")

    @app.route("/students/<int:sid>/edit", methods=["GET", "POST"])
    def student_edit(sid):
        s = dict(get_student(sid))
        ex = db().execute("SELECT * FROM student_extra WHERE student_id=?", (sid,)).fetchone()
        s.update(roll=ex["roll"] if ex else "", gender=ex["gender"] if ex else "", address=ex["address"] if ex else "",
                 batch_ids=[b[0] for b in db().execute("SELECT batch_id FROM student_batches WHERE student_id=?", (sid,))])
        err = None
        if request.method == "POST":
            v, err = parse(request.form)
            if not err:
                db().execute(UPD, v + (sid,))
                db().commit()
                save_extra(db, sid, request.form)
                return redirect(f"/students/{sid}")
            s = keep(s)
        return form_page(db, s, err, f"/students/{sid}/edit", "edit_student_title")

    @app.route("/students/<int:sid>/inactive", methods=["POST"])
    def student_inactive(sid):
        get_student(sid)
        cols = "id,name,cls,parent_name,parent_phone,monthly_fee,admission_date,acad_session,session_end"
        db().execute(f"INSERT OR REPLACE INTO records({cols},archived_on) SELECT {cols},? FROM students WHERE id=?",
                     (date.today().isoformat(), sid))
        db().execute("DELETE FROM students WHERE id=?", (sid,))
        db().commit()
        return redirect("/students?status=inactive")

    @app.route("/students/<int:sid>/delete", methods=["POST"])
    def student_delete(sid):
        get_student(sid)
        for tbl in ("attendance", "payments", "student_batches"):
            db().execute(f"DELETE FROM {tbl} WHERE student_id=?", (sid,))
        db().execute("DELETE FROM student_extra WHERE student_id=?", (sid,))
        db().execute("DELETE FROM students WHERE id=?", (sid,))
        db().commit()
        return redirect("/students")
