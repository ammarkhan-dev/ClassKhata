import sqlite3
from flask import Flask, render_template, request, redirect, g

app = Flask(__name__)
COACHING_NAME = "ClassKhata"
DB = "classkhata.db"

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close(e):
    d = g.pop("db", None)
    if d:
        d.close()

def init():
    with sqlite3.connect(DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS students(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, cls INTEGER NOT NULL,
            parent_phone TEXT, monthly_fee INTEGER DEFAULT 0)""")

@app.context_processor
def inject():
    return dict(coaching=COACHING_NAME)

@app.route("/")
def home():
    rows = db().execute("SELECT cls, COUNT(*) n FROM students GROUP BY cls ORDER BY cls").fetchall()
    total = sum(r["n"] for r in rows)
    return render_template("home.html", total=total, rows=rows)

@app.route("/students", methods=["GET", "POST"])
def students():
    if request.method == "POST":
        name = request.form["name"].strip()
        if name:
            db().execute(
                "INSERT INTO students(name,cls,parent_phone,monthly_fee) VALUES(?,?,?,?)",
                (name, int(request.form["cls"]), request.form["phone"].strip(),
                 int(request.form.get("fee") or 0)))
            db().commit()
        return redirect("/students")
    rows = db().execute("SELECT * FROM students ORDER BY cls, name").fetchall()
    return render_template("students.html", rows=rows)

@app.route("/delete/<int:sid>", methods=["POST"])
def delete(sid):
    db().execute("DELETE FROM students WHERE id=?", (sid,))
    db().commit()
    return redirect("/students")

import hazri
hazri.setup(app, db)
import fees
fees.setup(app, db)
init()
app.run(host="0.0.0.0", port=5000)
