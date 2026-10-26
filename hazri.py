import calendar, re, sqlite3
from datetime import date, timedelta
from flask import render_template, request, redirect, abort, session
import store
from fees import MONTHS, WEEK, fmt

STATS = """(SELECT COUNT(*) FROM attendance x WHERE x.student_id=s.id AND x.status='P'
    AND (s.admission_date IS NULL OR x.day >= s.admission_date)) AS pres,
    (SELECT COUNT(*) FROM attendance y WHERE y.student_id=s.id AND y.status IN ('P','A')
    AND (s.admission_date IS NULL OR y.day >= s.admission_date)) AS tot"""

def pct(pres, tot):
    return round(100 * pres / tot) if tot else None

def lang_of():
    l = session.get("lang", "en")
    return l if l in MONTHS else "en"

def pick_day():
    try:
        d = date.fromisoformat(request.values.get("day", ""))
    except ValueError:
        d = date.today()
    return min(d, date.today()).isoformat()

def month_arg(val):
    if val and re.fullmatch(r"\d{4}-\d{2}", val):
        y, m = int(val[:4]), int(val[5:])
        if 1 <= m <= 12 and 2000 <= y <= 2100:
            return y, m
    t = date.today()
    return t.year, t.month

def short(lang, d):
    nm = MONTHS[lang][d.month - 1]
    return f"{d.day} {nm[:3] if lang == 'en' else nm}"

def band(x):
    return "g" if x >= 90 else ("m" if x >= 75 else "r")

def setup(app, db):
    with sqlite3.connect("classkhata.db") as c:
        c.execute("CREATE TABLE IF NOT EXISTS attendance(student_id INTEGER, day TEXT, status TEXT, PRIMARY KEY(student_id, day))")

    @app.route("/hazri")
    def hazri():
        today = date.today()
        day = pick_day()
        d = date.fromisoformat(day)
        mon = d - timedelta(days=d.weekday())
        week = []
        for i in range(7):
            w = mon + timedelta(days=i)
            week.append(dict(iso=w.isoformat(), n=w.day, wd=i, fut=w > today, sel=(w == d)))
        rows = db().execute("""SELECT s.cls, COUNT(*) total,
            SUM(CASE WHEN a.status='P' THEN 1 ELSE 0 END) p,
            SUM(CASE WHEN a.status='A' THEN 1 ELSE 0 END) a,
            SUM(CASE WHEN a.status='H' THEN 1 ELSE 0 END) h
            FROM students s LEFT JOIN attendance a ON a.student_id=s.id AND a.day=?
            GROUP BY s.cls ORDER BY s.cls""", (day,)).fetchall()
        cl = [dict(cls=r["cls"], total=r["total"], p=r["p"] or 0, a=r["a"] or 0, h=r["h"] or 0) for r in rows]
        for c in cl:
            c["marked"] = c["p"] + c["a"] + c["h"]
        P = sum(c["p"] for c in cl)
        A = sum(c["a"] for c in cl)
        return render_template("hazri_home.html", day=day, today=today.isoformat(), week=week,
            wd=d.weekday(), dnum=d.day, rows=cl, n_cls=len(cl),
            m_done=sum(1 for c in cl if c["marked"] >= c["total"]), pct_all=pct(P, P + A) or 0)

    @app.route("/hazri/<int:cls>")
    def hazri_class(cls):
        if cls not in (9, 10, 11, 12):
            abort(404)
        day = pick_day()
        rows = db().execute("""SELECT s.id, s.name, a.status FROM students s
            LEFT JOIN attendance a ON a.student_id=s.id AND a.day=?
            WHERE s.cls=? ORDER BY s.name COLLATE NOCASE""", (day, cls)).fetchall()
        return render_template("hazri_class.html", rows=rows, cls=cls, day=day,
                               dlabel=short(lang_of(), date.fromisoformat(day)))

    @app.route("/hazri/save", methods=["POST"])
    def hazri_save():
        day = pick_day()
        try:
            cls = int(request.form.get("cls", 0))
        except ValueError:
            cls = 0
        if cls not in (9, 10, 11, 12):
            return redirect("/hazri")
        for r in db().execute("SELECT id FROM students WHERE cls=?", (cls,)).fetchall():
            st = request.form.get(f"s{r['id']}", "")
            if st in ("P", "A", "H"):
                db().execute("INSERT OR REPLACE INTO attendance VALUES(?,?,?)", (r["id"], day, st))
            else:
                db().execute("DELETE FROM attendance WHERE student_id=? AND day=?", (r["id"], day))
        db().commit()
        return redirect(f"/hazri?day={day}")

    @app.route("/hazri/student/<int:sid>")
    def hazri_student(sid):
        lang = lang_of()
        s = db().execute(f"SELECT s.*, {STATS} FROM students s WHERE s.id=?", (sid,)).fetchone()
        if not s:
            abort(404)
        today = date.today()
        y, m = month_arg(request.args.get("month"))
        mine = {int(r["day"][8:]): r["status"] for r in db().execute(
            "SELECT day, status FROM attendance WHERE student_id=? AND day LIKE ?", (sid, f"{y:04d}-{m:02d}-%"))}
        vals = list(mine.values())
        pv = (y - 1, 12) if m == 1 else (y, m - 1)
        nx = (y + 1, 1) if m == 12 else (y, m + 1)
        return render_template("hazri_student.html", s=s, pct=pct(s["pres"], s["tot"]),
            month_label=f"{MONTHS[lang][m - 1]} {y}", weeks=calendar.Calendar(6).monthdayscalendar(y, m),
            marks=mine, wk=WEEK[lang], is_cur=(y == today.year and m == today.month), today=today,
            p=vals.count("P"), a=vals.count("A"), h=vals.count("H"),
            prev=f"{pv[0]:04d}-{pv[1]:02d}", nxt=f"{nx[0]:04d}-{nx[1]:02d}")

    @app.route("/hazri/overall")
    def hazri_overall():
        lang = lang_of()
        today = date.today()
        y, m = month_arg(request.args.get("month"))
        nd = calendar.monthrange(y, m)[1]
        rows = db().execute("""SELECT t.student_id sid, t.day, t.status, a.name, a.cls FROM attendance t
            JOIN (SELECT id, name, cls FROM students UNION SELECT id, name, cls FROM records) a ON a.id=t.student_id
            WHERE t.day LIKE ?""", (f"{y:04d}-{m:02d}-%",)).fetchall()
        cell, stu = {}, {}
        tot = [0, 0, 0]
        for r in rows:
            if r["status"] not in ("P", "A", "H"):
                continue
            i = "PAH".index(r["status"])
            cell.setdefault((r["cls"], int(r["day"][8:])), [0, 0, 0])[i] += 1
            stu.setdefault(r["sid"], dict(name=r["name"], cls=r["cls"], p=0, a=0, h=0))["pah"[i]] += 1
            tot[i] += 1
        matrix = []
        for c in sorted({k[0] for k in cell}):
            cells, cp, ca, ch = [], 0, 0, 0
            for d in range(1, nd + 1):
                v = cell.get((c, d))
                if not v:
                    cells.append(dict(t="–", k="n"))
                    continue
                cp, ca, ch = cp + v[0], ca + v[1], ch + v[2]
                if v[0] + v[1]:
                    x = round(100 * v[0] / (v[0] + v[1]))
                    cells.append(dict(t=str(x), k=band(x)))
                else:
                    cells.append(dict(t="H", k="h"))
            matrix.append(dict(cls=c, cells=cells, p=cp, a=ca, h=ch, pct=pct(cp, cp + ca)))
        srows = sorted(stu.values(), key=lambda s: (s["cls"], s["name"].lower()))
        for s in srows:
            s["pct"] = pct(s["p"], s["p"] + s["a"])
        pv = (y - 1, 12) if m == 1 else (y, m - 1)
        nx = (y + 1, 1) if m == 12 else (y, m + 1)
        avg = pct(tot[0], tot[0] + tot[1])
        inst = store.get("institute") or "ClassKhata"
        label = f"{MONTHS[lang][m - 1]} {y}"
        return render_template("hazri_overall.html", matrix=matrix, srows=srows, tot=tot, avg=avg,
            days=[dict(n=d, sun=date(y, m, d).weekday() == 6) for d in range(1, nd + 1)], nd=nd,
            month_label=label, rng=f"{fmt(date(y, m, 1), lang)} – {fmt(date(y, m, nd), lang)}",
            inst=inst, ini="".join(w[0] for w in inst.split()[:2]).upper() or "CK",
            gen=fmt(today, lang), who=session.get("name", ""), n_stu=len(srows), n_cls=len(matrix),
            prev=f"{pv[0]:04d}-{pv[1]:02d}", nxt=f"{nx[0]:04d}-{nx[1]:02d}",
            can_next=(y, m) < (today.year, today.month),
            share=f"{inst} · {label}: " + (f"{avg}%" if avg is not None else "—") + f" · P {tot[0]} · A {tot[1]} · H {tot[2]}")
