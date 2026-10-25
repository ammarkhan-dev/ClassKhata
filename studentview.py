from datetime import date, timedelta
from flask import render_template, request, redirect, abort, session
import store
from fees import sched, fmt, parse_d, MONTHS
from batches import days_text, time_text

def setup(app, db):
    def get(sid):
        s = db().execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not s:
            abort(404)
        return s

    @app.route("/students/<int:sid>/card")
    def student_card(sid):
        s = get(sid)
        lang = session.get("lang", "en")
        if lang not in MONTHS:
            lang = "en"
        ex = db().execute("SELECT * FROM student_extra WHERE student_id=?", (sid,)).fetchone()
        bl = [b["name"] for b in db().execute(
            "SELECT b.name FROM student_batches sb JOIN batches b ON b.id=sb.batch_id WHERE sb.student_id=? ORDER BY b.name", (sid,))]
        a = parse_d(s["admission_date"])
        inst = store.get("institute") or "ClassKhata"
        ini = "".join(w[0] for w in inst.split()[:2]).upper() or "CK"
        roll = ex["roll"] if ex and ex["roll"] else "—"
        share = f"{s['name']} · {s['cls']} · {roll}"
        if s["parent_phone"]:
            share += f" · +91 {s['parent_phone']}"
        return render_template("student_card.html", s=s, ex=ex, blist=bl,
                               sch=sched(db, sid, s["admission_date"]),
                               adm=fmt(a, lang) if a else "—", issued=fmt(date.today(), lang),
                               inst=inst, ini=ini, share=share)

    @app.route("/students/<int:sid>/batches", methods=["GET", "POST"])
    def student_batches(sid):
        s = get(sid)
        if request.method == "POST":
            db().execute("DELETE FROM student_batches WHERE student_id=?", (sid,))
            for b in request.form.getlist("batch"):
                if b.isdigit():
                    db().execute("INSERT OR IGNORE INTO student_batches VALUES(?,?)", (sid, int(b)))
            db().commit()
            return redirect(f"/students/{sid}")
        bl = [dict(id=r["id"], name=r["name"], days_s=days_text(r["days"]), time_s=time_text(r["t_from"], r["t_to"]))
              for r in db().execute("SELECT * FROM batches ORDER BY name COLLATE NOCASE")]
        sel = [r[0] for r in db().execute("SELECT batch_id FROM student_batches WHERE student_id=?", (sid,))]
        return render_template("student_batches.html", s=s, batches=bl, sel=sel)

    @app.route("/students/<int:sid>/absent", methods=["GET", "POST"])
    def student_absent(sid):
        s = get(sid)
        today = date.today()
        err, done, skipped = None, None, 0
        if request.method == "POST":
            try:
                a = date.fromisoformat(request.form.get("from", ""))
                b = date.fromisoformat(request.form.get("to", ""))
            except ValueError:
                a = b = None
            if not a or a > b or b > today or (b - a).days > 61:
                err = "err_range"
            else:
                done = 0
                adm = s["admission_date"] or "0000-00-00"
                d = a
                while d <= b:
                    iso = d.isoformat()
                    has = db().execute("""SELECT 1 FROM attendance x JOIN students t ON t.id=x.student_id
                        WHERE t.cls=? AND x.day=? LIMIT 1""", (s["cls"], iso)).fetchone()
                    if has and iso >= adm:
                        db().execute("INSERT OR REPLACE INTO attendance VALUES(?,?,?)", (sid, iso, "A"))
                        done += 1
                    else:
                        skipped += 1
                    d += timedelta(days=1)
                db().commit()
        return render_template("student_absent.html", s=s, err=err, done=done, skipped=skipped,
                               today=today.isoformat())
