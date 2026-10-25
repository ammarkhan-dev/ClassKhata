import sqlite3
from datetime import date
from flask import render_template, request, redirect, abort, session
from fees import fee_history, parse_d, MONTHS
from students import parse, cur_session, session_options, default_end, save_extra, form_page

COLS = "id,name,cls,parent_name,parent_phone,monthly_fee,admission_date,acad_session,session_end"

def archive(c, where, args):
    c.execute(f"INSERT OR REPLACE INTO records({COLS},archived_on) SELECT {COLS},? FROM students WHERE {where}",
              (date.today().isoformat(),) + tuple(args))
    c.execute(f"DELETE FROM students WHERE {where}", tuple(args))

def keep_form(s):
    f = request.form
    s.update(name=f.get("name", ""), cls=f.get("cls", "9"), parent_name=f.get("parent_name", ""),
             parent_phone=f.get("phone", ""), monthly_fee=f.get("fee", ""),
             admission_date=f.get("adm", ""), acad_session=f.get("ses", ""),
             session_end=f.get("end", ""))
    return s

def mlabel(lang, y, m):
    nm = MONTHS[lang][m - 1]
    return (nm if lang != "en" else nm[:3]) + " " + str(y)[2:]

def setup(app, db):
    with sqlite3.connect("classkhata.db") as c:
        c.execute("""CREATE TABLE IF NOT EXISTS records(
            id INTEGER PRIMARY KEY, name TEXT, cls INTEGER, parent_name TEXT,
            parent_phone TEXT, monthly_fee INTEGER, admission_date TEXT,
            acad_session TEXT, session_end TEXT, archived_on TEXT)""")

    @app.before_request
    def auto_archive():
        if request.endpoint == "static":
            return
        today = date.today().isoformat()
        c = sqlite3.connect("classkhata.db")
        try:
            if c.execute("SELECT 1 FROM students WHERE session_end IS NOT NULL AND session_end < ? LIMIT 1", (today,)).fetchone():
                archive(c, "session_end IS NOT NULL AND session_end < ?", (today,))
                c.commit()
        finally:
            c.close()

    def get_record(sid):
        r = db().execute("SELECT * FROM records WHERE id=?", (sid,)).fetchone()
        if not r:
            abort(404)
        return r

    @app.route("/records")
    def records():
        rows = db().execute("SELECT id, name, cls, acad_session FROM records ORDER BY acad_session DESC, cls, name COLLATE NOCASE").fetchall()
        groups = {}
        for r in rows:
            groups.setdefault(r["acad_session"] or "—", {}).setdefault(r["cls"], []).append(r)
        active = db().execute("SELECT acad_session ses, COUNT(*) n FROM students GROUP BY acad_session ORDER BY acad_session").fetchall()
        return render_template("records.html", groups=groups, active=active)

    @app.route("/records/end", methods=["POST"])
    def end_session():
        ses = request.form.get("ses", "") or None
        archive(db(), "acad_session IS ?", (ses,))
        db().commit()
        return redirect("/records")

    @app.route("/records/student/<int:sid>")
    def record_detail(sid):
        r = get_record(sid)
        lang = session.get("lang", "en")
        if lang not in MONTHS:
            lang = "en"
        end = parse_d(r["session_end"])
        upto = min(date.today(), end) if end else date.today()
        fee = r["monthly_fee"] or 0
        pm = {x["month"]: x["amt"] for x in db().execute(
            "SELECT month, SUM(amount) amt FROM payments WHERE student_id=? GROUP BY month", (sid,))}
        hist = fee_history(r["admission_date"], fee, pm, upto) if fee > 0 else []
        for h in hist:
            h["label"] = mlabel(lang, h["y"], h["m"])
        info = dict(paid_n=sum(1 for h in hist if h["st"] == "paid"), tot_n=len(hist),
                    total_paid=sum(pm.values()),
                    unpaid=sum(h["baaki"] for h in hist if h["st"] == "due"))
        adm = r["admission_date"] or "0000-00-00"
        lim = r["session_end"] or "9999-12-31"
        days = {x["mon"]: x["n"] for x in db().execute("""SELECT substr(day,1,7) mon, COUNT(DISTINCT day) n
            FROM attendance WHERE day >= ? AND day <= ? AND student_id IN (
              SELECT id FROM students WHERE cls=? AND acad_session IS ?
              UNION SELECT id FROM records WHERE cls=? AND acad_session IS ?)
            GROUP BY mon""", (adm, lim, r["cls"], r["acad_session"], r["cls"], r["acad_session"]))}
        pres = {x["mon"]: x["n"] for x in db().execute("""SELECT substr(day,1,7) mon, COUNT(*) n
            FROM attendance WHERE student_id=? AND status='P' AND day >= ? AND day <= ?
            GROUP BY mon""", (sid, adm, lim))}
        months = []
        for mk in sorted(days):
            p = pres.get(mk, 0)
            months.append(dict(label=mlabel(lang, int(mk[:4]), int(mk[5:])), pres=p,
                               days=days[mk], pct=round(100 * p / days[mk])))
        td = sum(days.values())
        pct = round(100 * sum(pres.values()) / td) if td else None
        return render_template("record_detail.html", r=r, hist=hist, info=info, months=months, pct=pct)

    @app.route("/records/<int:sid>/restore", methods=["POST"])
    def record_restore(sid):
        r = get_record(sid)
        today = date.today().isoformat()
        end = r["session_end"] if r["session_end"] and r["session_end"] >= today else default_end(cur_session())
        db().execute(f"INSERT INTO students({COLS}) SELECT id,name,cls,parent_name,parent_phone,monthly_fee,admission_date,acad_session,? FROM records WHERE id=?", (end, sid))
        db().execute("DELETE FROM records WHERE id=?", (sid,))
        db().commit()
        return redirect(f"/students/{sid}")

    @app.route("/records/<int:sid>/readmit", methods=["GET", "POST"])
    def record_readmit(sid):
        r = get_record(sid)
        ses = cur_session()
        s = dict(name=r["name"], cls=min((r["cls"] or 9) + 1, 12), parent_name=r["parent_name"] or "",
                 parent_phone=r["parent_phone"] or "", monthly_fee=r["monthly_fee"] or "",
                 admission_date=date.today().isoformat(), acad_session=ses, session_end=default_end(ses))
        err = None
        if request.method == "POST":
            v, err = parse(request.form)
            if not err:
                cur = db().execute("INSERT INTO students(name,cls,parent_name,parent_phone,monthly_fee,admission_date,acad_session,session_end) VALUES(?,?,?,?,?,?,?,?)", v)
                db().commit()
                save_extra(db, cur.lastrowid, request.form)
                return redirect(f"/students?cls={v[1]}")
            s = keep_form(s)
        return form_page(db, s, err, f"/records/{sid}/readmit", "readmit_title")
        _unused = dict(
                               title_key="readmit_title", sessions=session_options(s.get("acad_session")))
