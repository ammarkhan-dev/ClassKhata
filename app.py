import sqlite3
from datetime import date
from flask import Flask, render_template, g

import os
app = Flask(__name__)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=bool(os.environ.get("CK_PROD")))
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

@app.context_processor
def inject():
    return dict(coaching=COACHING_NAME, institute=store.get("institute"))

import i18n, auth, students, hazri, fees, store, records, more, report, dash, batches, studentview, feesview

def _old_home():
    rows = db().execute("SELECT cls, COUNT(*) n FROM students GROUP BY cls").fetchall()
    counts = {r["cls"]: r["n"] for r in rows}
    att = {r["status"]: r["n"] for r in db().execute(
        "SELECT status, COUNT(*) n FROM attendance WHERE day=? GROUP BY status",
        (date.today().isoformat(),))}
    pn, pa = fees.pending_all(db)
    return render_template("home.html", total=sum(counts.values()), counts=counts,
                           p=att.get("P", 0), a=att.get("A", 0), pn=pn, pa=pa,
                           ses=students.cur_session())

i18n.setup(app)
auth.setup(app)
students.setup(app, db)
hazri.setup(app, db)
fees.setup(app, db)
records.setup(app, db)
more.setup(app, db)
report.setup(app, db)
dash.setup(app, db)
batches.setup(app, db)
studentview.setup(app, db)

feesview.setup(app, db)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
