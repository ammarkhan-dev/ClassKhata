import re, sqlite3
from datetime import date, timedelta
from urllib.parse import urlencode
from flask import render_template, request, redirect, abort, session, Response
import store
from fees import MONTHS, fmt, parse_d, fee_state, fee_history_s, sched, due_date, eligible, wa_link
from batches import days_text, time_text

def lang_of():
    l = session.get("lang", "en")
    return l if l in MONTHS else "en"

def to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

def short(lang, d):
    nm = MONTHS[lang][d.month - 1]
    return f"{d.day} {nm[:3] if lang == 'en' else nm}"

def setup(app, db):
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
    with sqlite3.connect("classkhata.db") as c:
        c.execute("CREATE TABLE IF NOT EXISTS student_photo(student_id INTEGER PRIMARY KEY, mime TEXT, data BLOB)")

    def get(sid):
        s = db().execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not s:
            abort(404)
        return s

    def fetch(table, q, cls, bid):
        sql = (f"SELECT t.id, t.name, t.cls, t.parent_phone, t.acad_session, x.roll FROM {table} t "
               "LEFT JOIN student_extra x ON x.student_id=t.id WHERE 1=1")
        args = []
        if q:
            like = "%" + q.replace("%", "").replace("_", "") + "%"
            sql += " AND (t.name LIKE ? OR x.roll LIKE ? OR t.parent_phone LIKE ?)"
            args += [like, like, like]
        if cls:
            sql += " AND t.cls=?"
            args.append(cls)
        if bid:
            sql += " AND t.id IN (SELECT student_id FROM student_batches WHERE batch_id=?)"
            args.append(bid)
        return db().execute(sql, args).fetchall()

    @app.route("/students")
    def students_list():
        stt = request.args.get("status", "active")
        if stt not in ("active", "inactive", "all"):
            stt = "active"
        fee = request.args.get("fee", "")
        if fee not in ("paid", "pending", "upcoming"):
            fee = ""
        srt = request.args.get("sort", "name")
        if srt not in ("name", "recent", "due"):
            srt = "name"
        q = request.args.get("q", "").strip()[:40]
        cls = to_int(request.args.get("cls"))
        cls = cls if cls in (9, 10, 11, 12) else None
        bid = to_int(request.args.get("batch"))
        state = fee_state(db)
        photos = {r[0] for r in db().execute("SELECT student_id FROM student_photo")}

        def card(r, inactive):
            o, st = (0, "") if inactive else state.get(r["id"], (0, "paid"))
            return dict(id=r["id"], name=r["name"], cls=r["cls"], phone=r["parent_phone"] or "",
                        roll=r["roll"] or "", ses=r["acad_session"] or "", inactive=inactive,
                        owed=o, fst=st, photo=r["id"] in photos)

        act = [card(r, False) for r in fetch("students", q, cls, bid)]
        ina = [card(r, True) for r in fetch("records", q, cls, bid)]
        if fee:
            act = [c for c in act if c["fst"] == fee]
            ina = []
        counts = dict(active=len(act), inactive=len(ina), all=len(act) + len(ina))
        rows = act if stt == "active" else (ina if stt == "inactive" else act + ina)
        if srt == "recent":
            rows.sort(key=lambda c: c["id"], reverse=True)
        elif srt == "due":
            rows.sort(key=lambda c: (-c["owed"], c["name"].lower()))
        else:
            rows.sort(key=lambda c: c["name"].lower())
        bl = [dict(id=b["id"], name=b["name"]) for b in db().execute("SELECT id, name FROM batches ORDER BY name COLLATE NOCASE")]
        bname = next((b["name"] for b in bl if b["id"] == bid), "")

        def href(**over):
            p = dict(status=stt, fee=fee, sort=srt, q=q, cls=cls or "", batch=bid or "")
            p.update(over)
            return "/students?" + urlencode({k: v for k, v in p.items() if v not in ("", None)})

        return render_template("students.html", rows=rows, status=stt, fee=fee, srt=srt, q=q, cls=cls,
                               bid=bid, counts=counts, batches=bl, bname=bname, href=href,
                               owed_total=sum(c["owed"] for c in rows))

    @app.route("/students/<int:sid>")
    def student_profile(sid):
        s = get(sid)
        lang = lang_of()
        today = date.today()
        fee = s["monthly_fee"] or 0
        pm = {r["month"]: r["amt"] for r in db().execute(
            "SELECT month, SUM(amount) amt FROM payments WHERE student_id=? GROUP BY month", (sid,))}
        pids = {r["month"]: r["pid"] for r in db().execute(
            "SELECT month, MAX(id) pid FROM payments WHERE student_id=? GROUP BY month", (sid,))}
        a0, _x = sched(db, sid, s["admission_date"])
        hist = fee_history_s(db, sid, s["admission_date"], fee, pm, today) if fee > 0 else []
        entries = []
        for h in hist:
            ny, nm = (h["y"] + 1, 1) if h["m"] == 12 else (h["y"], h["m"] + 1)
            end = due_date(a0, ny, nm)
            entries.append(dict(key=h["key"], label=f"{MONTHS[lang][h['m'] - 1]} {h['y']}",
                                span=f"{short(lang, h['due'])} – {short(lang, end)}",
                                baaki=h["baaki"], st=h["st"], pid=pids.get(h["key"])))
        due = [h for h in hist if h["st"] == "due"]
        up = sum(h["baaki"] for h in hist if h["st"] == "soon")
        if fee > 0 and not hist:
            up = fee
        remind = wa_link(s, due[0]["baaki"], due[0]["due"], due[0]["y"], due[0]["m"], lang) if due else ""
        adm = s["admission_date"] or "0000-00-00"
        r = db().execute("""SELECT
            (SELECT COUNT(*) FROM attendance x WHERE x.student_id=? AND x.status='P' AND x.day>=?) AS pres,
            (SELECT COUNT(DISTINCT y.day) FROM attendance y JOIN students t ON t.id=y.student_id
             WHERE t.cls=? AND y.day>=?) AS tot""", (sid, adm, s["cls"], adm)).fetchone()
        ex = db().execute("SELECT * FROM student_extra WHERE student_id=?", (sid,)).fetchone()
        has_photo = db().execute("SELECT 1 FROM student_photo WHERE student_id=?", (sid,)).fetchone() is not None
        return render_template("student_detail.html", s=s, ex=ex, entries=entries[::-1], fee=fee,
            remind=remind, has_photo=has_photo, pend=sum(h["baaki"] for h in due), upc=up,
            coll=sum(pm.values()), pct=round(100 * r["pres"] / r["tot"]) if r["tot"] else None)

    @app.route("/students/<int:sid>/pay/<month>", methods=["POST"])
    def student_pay(sid, month):
        s = get(sid)
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            abort(404)
        y, m = int(month[:4]), int(month[5:])
        today = date.today()
        a0, _x = sched(db, sid, s["admission_date"])
        if (y, m) > (today.year, today.month) or not eligible(a0, y, m):
            abort(404)
        paid = db().execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE student_id=? AND month=?",
                            (sid, month)).fetchone()[0]
        left = (s["monthly_fee"] or 0) - paid
        if left > 0:
            db().execute("INSERT INTO payments(student_id,month,amount,paid_on) VALUES(?,?,?,?)",
                         (sid, month, left, today.isoformat()))
            db().commit()
        return redirect(f"/students/{sid}")

    @app.route("/students/<int:sid>/card")
    def student_card(sid):
        s = get(sid)
        lang = lang_of()
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
        has_photo = db().execute("SELECT 1 FROM student_photo WHERE student_id=?", (sid,)).fetchone() is not None
        return render_template("student_card.html", s=s, ex=ex, blist=bl, sch=sched(db, sid, s["admission_date"]),
                               adm=fmt(a, lang) if a else "—", issued=fmt(date.today(), lang),
                               inst=inst, ini=ini, share=share, has_photo=has_photo)

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

    @app.route("/receipt/<int:pid>")
    def receipt(pid):
        p = db().execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone()
        if not p:
            abort(404)
        st = db().execute("""SELECT name, cls, parent_name FROM students WHERE id=?
            UNION ALL SELECT name, cls, parent_name FROM records WHERE id=?""",
            (p["student_id"], p["student_id"])).fetchone()
        if not st:
            abort(404)
        lang = lang_of()
        try:
            mon = f"{MONTHS[lang][int(p['month'][5:7]) - 1]} {p['month'][:4]}"
        except (ValueError, IndexError):
            mon = p["month"]
        d = parse_d(p["paid_on"])
        on = fmt(d, lang) if d else ""
        inst = store.get("institute") or "ClassKhata"
        share = f"{inst}: {st['name']} · {mon} · ₹{p['amount']} · {on}"
        return render_template("receipt.html", p=p, st=st, no=f"{pid:05d}", mon=mon, on=on, inst=inst, share=share)

    @app.route("/students/<int:sid>/receipts")
    def receipts(sid):
        s = get(sid)
        lang = lang_of()
        rows = []
        for p in db().execute("SELECT id, month, amount, paid_on FROM payments WHERE student_id=? ORDER BY id DESC", (sid,)):
            try:
                lab = f"{MONTHS[lang][int(p['month'][5:7]) - 1]} {p['month'][:4]}"
            except (ValueError, IndexError):
                lab = p["month"]
            d = parse_d(p["paid_on"])
            rows.append(dict(id=p["id"], label=lab, amt=p["amount"], on=fmt(d, lang) if d else ""))
        return render_template("receipts.html", s=s, rows=rows)

    @app.route("/students/<int:sid>/photo", methods=["GET", "POST"])
    def photo(sid):
        if request.method == "POST":
            get(sid)
            f = request.files.get("photo")
            data = f.read(400001) if f else b""
            jpg = data[:3] == b"\xff\xd8\xff"
            png = data[:8] == b"\x89PNG\r\n\x1a\n"
            if not data or len(data) > 400000 or not (jpg or png):
                abort(400)
            db().execute("INSERT OR REPLACE INTO student_photo(student_id,mime,data) VALUES(?,?,?)",
                         (sid, "image/jpeg" if jpg else "image/png", data))
            db().commit()
            return ("", 204)
        r = db().execute("SELECT mime, data FROM student_photo WHERE student_id=?", (sid,)).fetchone()
        if not r:
            abort(404)
        resp = Response(r["data"], mimetype=r["mime"])
        resp.headers["Cache-Control"] = "private, no-cache"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp
