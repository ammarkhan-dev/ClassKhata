import sqlite3
from datetime import date
from flask import render_template, request, redirect, abort, session
from fees import fee_history, fmt, MONTHS

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

def digits10(s):
    d = "".join(ch for ch in s if ch.isdigit())
    if len(d) > 10 and d.startswith("91"):
        d = d[-10:]
    return d if len(d) == 10 else None

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
    except ValueError:
        return None, "err_date"
    try:
        cls = int(form.get("cls", 0))
    except ValueError:
        cls = 0
    if cls not in (9, 10, 11, 12):
        return None, "err_student_name"
    ses = form.get("ses", "").strip() or cur_session()
    return (name, cls, form.get("parent_name", "").strip(), phone, fee, adm, ses), None

def setup(app, db):
    with sqlite3.connect("classkhata.db") as c:
        c.execute("""CREATE TABLE IF NOT EXISTS students(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, cls INTEGER NOT NULL,
            parent_phone TEXT, monthly_fee INTEGER DEFAULT 0)""")
        have = [r[1] for r in c.execute("PRAGMA table_info(students)")]
        for col in ("parent_name", "admission_date", "acad_session"):
            if col not in have:
                c.execute(f"ALTER TABLE students ADD COLUMN {col} TEXT")

    def get_student(sid):
        s = db().execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not s:
            abort(404)
        return s

    def form_page(s, err, action, title_key):
        return render_template("student_form.html", s=s, err=err, action=action,
                               title_key=title_key,
                               sessions=session_options(s.get("acad_session")))

    def keep(s):
        f = request.form
        s.update(name=f.get("name", ""), cls=f.get("cls", "9"),
                 parent_name=f.get("parent_name", ""), parent_phone=f.get("phone", ""),
                 monthly_fee=f.get("fee", ""), admission_date=f.get("adm", ""),
                 acad_session=f.get("ses", ""))
        return s

    NEW = "INSERT INTO students(name,cls,parent_name,parent_phone,monthly_fee,admission_date,acad_session) VALUES(?,?,?,?,?,?,?)"
    UPD = "UPDATE students SET name=?,cls=?,parent_name=?,parent_phone=?,monthly_fee=?,admission_date=?,acad_session=? WHERE id=?"

    @app.route("/students")
    def students():
        q = request.args.get("q", "").strip()
        if q:
            like = "%" + q.replace("%", "").replace("_", "") + "%"
            found = db().execute("SELECT id, name, cls FROM students WHERE name LIKE ? ORDER BY name COLLATE NOCASE LIMIT 50", (like,)).fetchall()
            return render_template("students_home.html", q=q, found=found, counts={})
        rows = db().execute("SELECT cls, COUNT(*) n FROM students GROUP BY cls").fetchall()
        return render_template("students_home.html", q="", found=None,
                               counts={r["cls"]: r["n"] for r in rows})

    @app.route("/students/class/<int:cls>")
    def students_class(cls):
        if cls not in (9, 10, 11, 12):
            abort(404)
        rows = db().execute("SELECT id, name FROM students WHERE cls=? ORDER BY name COLLATE NOCASE", (cls,)).fetchall()
        return render_template("class_list.html", rows=rows, cls=cls)

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
        hist = fee_history(s["admission_date"], fee, pm, today) if fee > 0 else []
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
        return render_template("student_detail.html", s=s, hist=hist, info=info, att=r, pct=pct)

    @app.route("/students/add", methods=["GET", "POST"])
    def student_add():
        s = dict(name="", cls=9, parent_name="", parent_phone="", monthly_fee="",
                 admission_date=date.today().isoformat(), acad_session=cur_session())
        err = None
        if request.method == "POST":
            v, err = parse(request.form)
            if not err:
                db().execute(NEW, v)
                db().commit()
                return redirect(f"/students/class/{v[1]}")
            s = keep(s)
        return form_page(s, err, "/students/add", "add_student_title")

    @app.route("/students/<int:sid>/edit", methods=["GET", "POST"])
    def student_edit(sid):
        s = dict(get_student(sid))
        err = None
        if request.method == "POST":
            v, err = parse(request.form)
            if not err:
                db().execute(UPD, v + (sid,))
                db().commit()
                return redirect(f"/students/{sid}")
            s = keep(s)
        return form_page(s, err, f"/students/{sid}/edit", "edit_student_title")

    @app.route("/students/<int:sid>/delete", methods=["POST"])
    def student_delete(sid):
        cls = get_student(sid)["cls"]
        for tbl in ("attendance", "payments"):
            db().execute(f"DELETE FROM {tbl} WHERE student_id=?", (sid,))
        db().execute("DELETE FROM students WHERE id=?", (sid,))
        db().commit()
        return redirect(f"/students/class/{cls}")
