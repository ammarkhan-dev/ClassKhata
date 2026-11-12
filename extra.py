"""BatchBook - previous due + extra fee entries.
They live in table extra_dues; payments use month key 'X<id>'.  fees.fee_history_s adds them
at the START of the history, so every page that sums 'due' baaki includes them automatically."""
import re
import sqlite3
from datetime import date, datetime
from flask import abort, redirect, render_template, request, session
import store

UI = {
    "en": dict(title="Previous due / extra fee", sub="Added to the pending amount", kind="Type", prev="Previous due",
               ext="Extra fee (exam, book...)", label="Name", amount="Amount (₹)", add="Add", list="Entries",
               none="Nothing added yet.", paid="Paid", pending="Pending", delete="Delete", back="Back",
               ph="e.g. Exam fee", dflt="Previous due", hint="Collect it from the student's page like a normal fee.",
               cant="Paid entries cannot be deleted. Undo the payment first."),
    "hi": dict(title="पुराना बकाया / अतिरिक्त फ़ीस", sub="बकाया राशि में जुड़ जाएगा", kind="प्रकार", prev="पुराना बकाया",
               ext="अतिरिक्त फ़ीस (परीक्षा, किताब...)", label="नाम", amount="राशि (₹)", add="जोड़ें", list="प्रविष्टियाँ",
               none="अभी कुछ नहीं जोड़ा।", paid="जमा", pending="बकाया", delete="हटाएँ", back="वापस",
               ph="जैसे परीक्षा फ़ीस", dflt="पुराना बकाया", hint="विद्यार्थी के पेज से सामान्य फ़ीस की तरह जमा करें।",
               cant="जमा हो चुकी प्रविष्टि हटाई नहीं जा सकती। पहले भुगतान वापस करें।"),
}
DDL = "CREATE TABLE IF NOT EXISTS extra_dues(id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, label TEXT, amount INTEGER, created TEXT)"


def ok(key):
    return bool(re.fullmatch(r"X\d{1,9}", key or ""))


def _rows(db, sid):
    try:
        return db().execute("SELECT * FROM extra_dues WHERE student_id=? ORDER BY id", (sid,)).fetchall()
    except sqlite3.Error:
        try:
            db().execute(DDL); db().commit()
        except sqlite3.Error:
            pass
        return []


def entries(db, sid, pm, today):
    out = []
    for r in _rows(db, sid):
        try:
            d = date.fromisoformat(r["created"])
        except (TypeError, ValueError):
            d = today
        key = "X%d" % r["id"]
        paid = pm.get(key, 0)
        b = max((r["amount"] or 0) - paid, 0)
        out.append(dict(y=d.year, m=d.month, key=key, due=d, paid=paid, baaki=b,
                        st="paid" if b == 0 else "due", label=r["label"], extra=True))
    return out


def pay(db, sid, key, mode=""):
    if not ok(key):
        abort(404)
    r = db().execute("SELECT * FROM extra_dues WHERE id=? AND student_id=?", (int(key[1:]), sid)).fetchone()
    if not r:
        abort(404)
    paid = db().execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE student_id=? AND month=?", (sid, key)).fetchone()[0]
    left = (r["amount"] or 0) - paid
    if left > 0:
        try:
            db().execute("INSERT INTO payments(student_id,month,amount,paid_on,mode) VALUES(?,?,?,?,?)",
                         (sid, key, left, date.today().isoformat(), mode or None))
        except sqlite3.Error:
            db().execute("INSERT INTO payments(student_id,month,amount,paid_on) VALUES(?,?,?,?)",
                         (sid, key, left, date.today().isoformat()))
        db().commit()


def setup(app, db=None):
    try:
        c = sqlite3.connect("classkhata.db"); c.execute(DDL); c.commit(); c.close()
    except sqlite3.Error:
        pass

    def con():
        c = sqlite3.connect("classkhata.db"); c.row_factory = sqlite3.Row; c.execute(DDL)
        return c

    @app.route("/students/<int:sid>/extra", methods=["GET", "POST"])
    def extra_page(sid):
        lg = "hi" if session.get("lang") == "hi" else "en"
        L = UI[lg]
        c = con()
        s = c.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not s:
            c.close(); abort(404)
        err = ""
        if request.method == "POST":
            kind = request.form.get("kind", "prev")
            label = request.form.get("label", "").strip()[:40]
            try:
                amt = int(float(request.form.get("amount", "0") or 0))
            except ValueError:
                amt = 0
            if kind == "prev" and not label:
                label = L["dflt"]
            if amt <= 0 or amt > 10000000 or not label:
                err = "x"
            else:
                c.execute("INSERT INTO extra_dues(student_id,label,amount,created) VALUES(?,?,?,?)",
                          (sid, label, amt, date.today().isoformat()))
                c.commit(); c.close()
                return redirect("/students/%d/extra" % sid)
        pm = {r["month"]: r["amt"] for r in c.execute("SELECT month, SUM(amount) amt FROM payments WHERE student_id=? GROUP BY month", (sid,))}
        rows = [dict(id=r["id"], label=r["label"], amount=r["amount"], paid=pm.get("X%d" % r["id"], 0), created=r["created"])
                for r in c.execute("SELECT * FROM extra_dues WHERE student_id=? ORDER BY id DESC", (sid,))]
        c.close()
        return render_template("extra_dues.html", L=L, s=s, rows=rows, err=err)

    @app.route("/students/<int:sid>/extra/<int:eid>/delete", methods=["POST"])
    def extra_delete(sid, eid):
        c = con()
        paid = c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE student_id=? AND month=?", (sid, "X%d" % eid)).fetchone()[0]
        if not paid:
            c.execute("DELETE FROM extra_dues WHERE id=? AND student_id=?", (eid, sid)); c.commit()
        c.close()
        return redirect("/students/%d/extra" % sid)
