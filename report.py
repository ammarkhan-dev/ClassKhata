import re
from datetime import date
from flask import render_template, request, session
from fees import fee_history, fee_history_s, fmt, MONTHS
from hazri import STATS, pct

def setup(app, db):
    @app.route("/report")
    def report():
        lang = session.get("lang", "en")
        if lang not in MONTHS:
            lang = "en"
        today = date.today()
        val = request.args.get("month", "")
        if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", val) and 2000 <= int(val[:4]) <= 2100:
            y, m = int(val[:4]), int(val[5:])
        else:
            y, m = today.year, today.month
        mk = f"{y:04d}-{m:02d}"
        pay = {}
        for p in db().execute("SELECT student_id sid, month, SUM(amount) amt FROM payments GROUP BY student_id, month"):
            pay.setdefault(p["sid"], {})[p["month"]] = p["amt"]
        rows = db().execute(f"""SELECT s.id, s.name, s.cls, s.monthly_fee, s.admission_date, {STATS}
            FROM students s ORDER BY s.cls, s.name COLLATE NOCASE""").fetchall()
        classes = {}
        for r in rows:
            fee = r["monthly_fee"] or 0
            mine = pay.get(r["id"], {})
            hist = fee_history_s(db, r["id"], r["admission_date"], fee, mine, today) if fee > 0 else []
            cur = next((h for h in hist if h["key"] == mk), None)
            g = classes.setdefault(r["cls"], dict(rows=[], collected=0, pending=0, pcts=[]))
            item = dict(name=r["name"], st=cur["st"] if cur else ("nofee" if fee == 0 else "none"),
                        owe=cur["baaki"] if cur else 0,
                        total=sum(h["baaki"] for h in hist if h["st"] == "due"),
                        pct=pct(r["pres"], r["tot"]))
            g["rows"].append(item)
            g["collected"] += mine.get(mk, 0)
            if item["st"] == "due":
                g["pending"] += item["owe"]
            if item["pct"] is not None:
                g["pcts"].append(item["pct"])
        allp = []
        tot = dict(n=0, collected=0, pending=0)
        for g in classes.values():
            g["n"] = len(g["rows"])
            g["avg"] = round(sum(g["pcts"]) / len(g["pcts"])) if g["pcts"] else None
            allp += g["pcts"]
            tot["n"] += g["n"]
            tot["collected"] += g["collected"]
            tot["pending"] += g["pending"]
        tot["avg"] = round(sum(allp) / len(allp)) if allp else None
        return render_template("report.html", classes=classes, tot=tot, mk=mk,
                               month_label=f"{MONTHS[lang][m - 1]} {y}", today_label=fmt(today, lang))
