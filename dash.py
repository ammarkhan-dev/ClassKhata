from datetime import date, datetime, timedelta
from flask import render_template
import fees
from more import backup_info

def greeting():
    h = datetime.now().hour
    return "greet_morning" if h < 12 else ("greet_afternoon" if h < 17 else "greet_evening")

def alert_list(db):
    today = date.today()
    out = []
    n, amt = fees.pending_all(db)
    if n:
        out.append(dict(key="al_fees", n=n, amt=f"{amt:,}", url="/fees"))
    rows = db().execute("""SELECT SUM(CASE WHEN a.status IS NOT NULL THEN 1 ELSE 0 END) m
        FROM students s LEFT JOIN attendance a ON a.student_id=s.id AND a.day=?
        GROUP BY s.cls""", (today.isoformat(),)).fetchall()
    k = sum(1 for r in rows if not r["m"])
    if k:
        out.append(dict(key="al_att", n=k, amt="", url="/hazri"))
    if rows and backup_info()[1]:
        out.append(dict(key="al_backup", n=0, amt="", url="/backup"))
    soon = db().execute("SELECT COUNT(*) FROM students WHERE session_end BETWEEN ? AND ?",
                        (today.isoformat(), (today + timedelta(days=30)).isoformat())).fetchone()[0]
    if soon:
        out.append(dict(key="al_end", n=soon, amt="", url="/records"))
    return out

def setup(app, db):
    def q(sql, a=()):
        return db().execute(sql, a).fetchone()[0]

    @app.route("/")
    def home():
        today = date.today().isoformat()
        month = date.today().replace(day=1).isoformat()
        p = q("SELECT COUNT(*) FROM attendance a JOIN students s ON s.id=a.student_id WHERE a.day=? AND a.status='P'", (today,))
        marked = q("SELECT COUNT(*) FROM attendance a JOIN students s ON s.id=a.student_id WHERE a.day=?", (today,))
        pn, pa = fees.pending_all(db)
        return render_template("home.html", greet=greeting(), p=p,
            pct=round(100 * p / marked) if marked else 0, pa=pa,
            total=q("SELECT COUNT(*) FROM students"), ncls=q("SELECT COUNT(DISTINCT cls) FROM students"),
            today_coll=q("SELECT COALESCE(SUM(amount),0) FROM payments WHERE paid_on=?", (today,)),
            month_coll=q("SELECT COALESCE(SUM(amount),0) FROM payments WHERE paid_on>=?", (month,)),
            n_alerts=len(alert_list(db)))

    @app.route("/alerts")
    def alerts():
        return render_template("alerts.html", items=alert_list(db))
