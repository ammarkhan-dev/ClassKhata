import sqlite3
from datetime import date
from flask import render_template, request, redirect

def setup(app, db):
    with sqlite3.connect("classkhata.db") as c:
        c.execute("""CREATE TABLE IF NOT EXISTS attendance(
            student_id INTEGER, day TEXT, status TEXT,
            PRIMARY KEY(student_id, day))""")

    @app.route("/hazri")
    def hazri():
        cls = int(request.args.get("cls", 9))
        day = request.args.get("day", date.today().isoformat())
        rows = db().execute("""SELECT s.id, s.name, a.status FROM students s
            LEFT JOIN attendance a ON a.student_id=s.id AND a.day=?
            WHERE s.cls=? ORDER BY s.name""", (day, cls)).fetchall()
        p = sum(1 for r in rows if r["status"] == "P")
        a = sum(1 for r in rows if r["status"] == "A")
        return render_template("hazri.html", rows=rows, cls=cls, day=day, p=p, a=a)

    @app.route("/mark", methods=["POST"])
    def mark():
        sid = int(request.form["sid"])
        day = request.form["day"]
        cls = request.form["cls"]
        db().execute("INSERT OR REPLACE INTO attendance VALUES(?,?,?)",
                     (sid, day, request.form["status"]))
        db().commit()
        return redirect(f"/hazri?cls={cls}&day={day}")
