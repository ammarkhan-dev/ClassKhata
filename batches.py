import sqlite3
from flask import render_template, request, redirect

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def t12(s):
    try:
        h, m = int(s[:2]), int(s[3:5])
    except (ValueError, TypeError):
        return ""
    return f"{(h % 12) or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"

def days_text(d):
    have = (d or "").split(",")
    ds = [x for x in DAYS if x in have]
    return "/".join(ds) if ds else "—"

def time_text(a, b):
    return f"{t12(a)} – {t12(b)}" if a and b else ""

def valid_time(s):
    return s if len(s) == 5 and s[2] == ":" and s[:2].isdigit() and s[3:].isdigit() else ""

def init():
    with sqlite3.connect("classkhata.db") as c:
        c.execute("CREATE TABLE IF NOT EXISTS batches(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, days TEXT, t_from TEXT, t_to TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS student_batches(student_id INTEGER, batch_id INTEGER, PRIMARY KEY(student_id, batch_id))")
        c.execute("CREATE TABLE IF NOT EXISTS student_extra(student_id INTEGER PRIMARY KEY, roll TEXT, gender TEXT, address TEXT)")

def setup(app, db):
    init()

    def safe_next(n):
        return n if n and n.startswith("/") and not n.startswith("//") else "/batches"

    def save(bid):
        f = request.form
        name = f.get("name", "").strip()[:60]
        if not name:
            return "err_batch_name"
        days = ",".join(d for d in DAYS if d in f.getlist("day"))
        a, b = valid_time(f.get("t_from", "")), valid_time(f.get("t_to", ""))
        if bid is None:
            db().execute("INSERT INTO batches(name,days,t_from,t_to) VALUES(?,?,?,?)", (name, days, a, b))
        else:
            db().execute("UPDATE batches SET name=?,days=?,t_from=?,t_to=? WHERE id=?", (name, days, a, b, bid))
        db().commit()
        return None

    @app.route("/batches")
    def batches():
        rows = db().execute("""SELECT b.*, (SELECT COUNT(*) FROM student_batches sb
            JOIN students s ON s.id=sb.student_id WHERE sb.batch_id=b.id) n
            FROM batches b ORDER BY b.name COLLATE NOCASE""").fetchall()
        items = [dict(id=r["id"], name=r["name"], n=r["n"], days_s=days_text(r["days"]),
                      time_s=time_text(r["t_from"], r["t_to"])) for r in rows]
        return render_template("batches.html", rows=items)

    @app.route("/batches/new", methods=["GET", "POST"])
    def batch_new():
        nxt = request.values.get("next", "")
        err = None
        sel = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        if request.method == "POST":
            err = save(None)
            if not err:
                return redirect(safe_next(nxt))
            sel = request.form.getlist("day")
        return render_template("batch_form.html", b=None, err=err, nxt=nxt, DAYS=DAYS, sel=sel)

    @app.route("/batches/<int:bid>/edit", methods=["GET", "POST"])
    def batch_edit(bid):
        b = db().execute("SELECT * FROM batches WHERE id=?", (bid,)).fetchone()
        if not b:
            return redirect("/batches")
        err = None
        sel = (b["days"] or "").split(",")
        if request.method == "POST":
            err = save(bid)
            if not err:
                return redirect("/batches")
            sel = request.form.getlist("day")
        return render_template("batch_form.html", b=b, err=err, nxt="", DAYS=DAYS, sel=sel)

    @app.route("/batches/<int:bid>/delete", methods=["POST"])
    def batch_delete(bid):
        db().execute("DELETE FROM student_batches WHERE batch_id=?", (bid,))
        db().execute("DELETE FROM batches WHERE id=?", (bid,))
        db().commit()
        return redirect("/batches")
