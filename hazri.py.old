import re, sqlite3, calendar
from datetime import date
from flask import render_template, request, redirect, abort, session
from fees import MONTHS, WEEK

STATS = """(SELECT COUNT(*) FROM attendance x WHERE x.student_id=s.id AND x.status='P'
    AND (s.admission_date IS NULL OR x.day >= s.admission_date)) AS pres,
    (SELECT COUNT(DISTINCT y.day) FROM attendance y JOIN students t ON t.id=y.student_id
    WHERE t.cls=s.cls AND (s.admission_date IS NULL OR y.day >= s.admission_date)) AS tot"""

def pct(pres, tot):
    return round(100 * pres / tot) if tot else None

def pick_day():
    try:
        d = date.fromisoformat(request.values.get("day", ""))
    except ValueError:
        d = date.today()
    return min(d, date.today()).isoformat()

def month_arg(val):
    if val and re.fullmatch(r"\d{4}-\d{2}", val):
        y, m = int(val[:4]), int(val[5:])
        if 1 <= m <= 12 and 2000 <= y <= 2100:
            return y, m
    t = date.today()
    return t.year, t.month

def setup(app, db):
    with sqlite3.connect("classkhata.db") as c:
        c.execute("""CREATE TABLE IF NOT EXISTS attendance(
            student_id INTEGER, day TEXT, status TEXT,
            PRIMARY KEY(student_id, day))""")

    @app.route("/hazri")
    def hazri():
        day = pick_day()
        rows = db().execute("""SELECT s.cls, COUNT(*) total,
            SUM(CASE WHEN a.status IS NOT NULL THEN 1 ELSE 0 END) marked
            FROM students s LEFT JOIN attendance a ON a.student_id=s.id AND a.day=?
            GROUP BY s.cls""", (day,)).fetchall()
        info = {r["cls"]: (r["total"], r["marked"] or 0) for r in rows}
        return render_template("hazri_home.html", day=day, info=info,
                               today=date.today().isoformat())

    @app.route("/hazri/<int:cls>")
    def hazri_class(cls):
        if cls not in (9, 10, 11, 12):
            abort(404)
        day = pick_day()
        rows = db().execute(f"""SELECT s.id, s.name, a.status, {STATS}
            FROM students s LEFT JOIN attendance a ON a.student_id=s.id AND a.day=?
            WHERE s.cls=? ORDER BY s.name COLLATE NOCASE""", (day, cls)).fetchall()
        items = [dict(id=r["id"], name=r["name"], status=r["status"],
                      pct=pct(r["pres"], r["tot"])) for r in rows]
        p = sum(1 for i in items if i["status"] == "P")
        a = sum(1 for i in items if i["status"] == "A")
        return render_template("hazri_class.html", rows=items, cls=cls, day=day,
                               p=p, a=a, today=date.today().isoformat())

    @app.route("/hazri/student/<int:sid>")
    def hazri_student(sid):
        lang = session.get("lang", "en")
        if lang not in MONTHS:
            lang = "en"
        s = db().execute(f"SELECT s.*, {STATS} FROM students s WHERE s.id=?", (sid,)).fetchone()
        if not s:
            abort(404)
        today = date.today()
        y, m = month_arg(request.args.get("month"))
        like = f"{y:04d}-{m:02d}-%"
        adm = s["admission_date"] or "0000-00-00"
        mine = {r["day"]: r["status"] for r in db().execute(
            "SELECT day, status FROM attendance WHERE student_id=? AND day LIKE ?", (sid, like))}
        cdays = [r[0] for r in db().execute(
            """SELECT DISTINCT y.day FROM attendance y JOIN students t ON t.id=y.student_id
               WHERE t.cls=? AND y.day LIKE ? AND y.day >= ?""", (s["cls"], like, adm))]
        marks = {int(d[8:]): mine.get(d, "N") for d in cdays}
        p = sum(1 for v in marks.values() if v == "P")
        a = sum(1 for v in marks.values() if v == "A")
        pv = (y - 1, 12) if m == 1 else (y, m - 1)
        nx = (y + 1, 1) if m == 12 else (y, m + 1)
        return render_template("hazri_student.html", s=s, pct=pct(s["pres"], s["tot"]),
            month_label=f"{MONTHS[lang][m - 1]} {y}",
            weeks=calendar.Calendar(6).monthdayscalendar(y, m), marks=marks, wk=WEEK[lang],
            is_cur=(y == today.year and m == today.month), today=today,
            p=p, a=a, n=len(marks) - p - a,
            prev=f"{pv[0]:04d}-{pv[1]:02d}", nxt=f"{nx[0]:04d}-{nx[1]:02d}")

    @app.route("/mark", methods=["POST"])
    def mark():
        day = pick_day()
        st = request.form.get("status")
        try:
            sid = int(request.form.get("sid", 0))
        except ValueError:
            sid = 0
        s = db().execute("SELECT id, cls FROM students WHERE id=?", (sid,)).fetchone()
        if not s:
            return redirect("/hazri")
        if st in ("P", "A"):
            db().execute("INSERT OR REPLACE INTO attendance VALUES(?,?,?)", (s["id"], day, st))
            db().commit()
        return redirect(f"/hazri/{s['cls']}?day={day}#s{s['id']}")

    @app.route("/mark_all", methods=["POST"])
    def mark_all():
        day = pick_day()
        try:
            cls = int(request.form.get("cls", 0))
        except ValueError:
            cls = 0
        if cls not in (9, 10, 11, 12):
            return redirect("/hazri")
        db().execute("""INSERT OR IGNORE INTO attendance(student_id, day, status)
            SELECT id, ?, 'P' FROM students WHERE cls=?""", (day, cls))
        db().commit()
        return redirect(f"/hazri/{cls}?day={day}")
