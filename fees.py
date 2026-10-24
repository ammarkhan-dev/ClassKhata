import sqlite3
from datetime import date
from urllib.parse import quote
from flask import render_template, request, redirect

def setup(app, db):
    with sqlite3.connect("classkhata.db") as c:
        c.execute("""CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER, month TEXT, amount INTEGER, paid_on TEXT)""")

    @app.route("/fees")
    def fees():
        month = request.args.get("month", date.today().strftime("%Y-%m"))
        rows = db().execute("""SELECT s.id, s.name, s.cls, s.parent_phone, s.monthly_fee,
            COALESCE((SELECT SUM(amount) FROM payments p
                      WHERE p.student_id=s.id AND p.month=?), 0) AS paid
            FROM students s ORDER BY s.cls, s.name""", (month,)).fetchall()
        items = []
        for r in rows:
            baaki = max(r["monthly_fee"] - r["paid"], 0)
            phone = "".join(ch for ch in (r["parent_phone"] or "") if ch.isdigit())
            if len(phone) == 10:
                phone = "91" + phone
            link = ""
            if phone and baaki > 0:
                msg = f"Namaste, {r['name']} ki {month} ki fees Rs {baaki} baaki hai. Kripya jama kar dein. Dhanyavaad."
                link = f"https://wa.me/{phone}?text={quote(msg)}"
            items.append(dict(id=r["id"], name=r["name"], cls=r["cls"],
                              fee=r["monthly_fee"], paid=r["paid"],
                              baaki=baaki, link=link))
        tp = sum(i["paid"] for i in items)
        tb = sum(i["baaki"] for i in items)
        return render_template("fees.html", items=items, month=month,
                               total_paid=tp, total_baaki=tb)

    @app.route("/pay", methods=["POST"])
    def pay():
        month = request.form["month"]
        amt = int(request.form.get("amount") or 0)
        if amt > 0:
            db().execute(
                "INSERT INTO payments(student_id,month,amount,paid_on) VALUES(?,?,?,?)",
                (int(request.form["sid"]), month, amt, date.today().isoformat()))
            db().commit()
        return redirect(f"/fees?month={month}")
