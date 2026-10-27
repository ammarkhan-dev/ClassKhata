import calendar, re
from datetime import date, timedelta
from urllib.parse import urlencode
from flask import render_template, request, redirect, abort, session
from fees import MONTHS, WEEK, parse_d, fee_history_s, sched, due_date, eligible, owed_map, wa_link

def lang_of():
    l = session.get("lang", "en")
    return l if l in MONTHS else "en"

def to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

def kf(n):
    n = int(n or 0)
    if n >= 100000:
        return "₹" + f"{n / 100000:.1f}".rstrip("0").rstrip(".") + "L"
    if n >= 1000:
        return "₹" + f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "k"
    return f"₹{n}"

def sdm(lang, d):
    nm = MONTHS[lang][d.month - 1]
    return f"{d.day} {nm[:3] if lang == 'en' else nm}"

def safe_next(n):
    return n if n and n.startswith("/fees") and not n.startswith("//") else "/fees"

def mkey_ok(s):
    return bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", s or ""))

def setup(app, db):
    def filtered(q, cls, bid):
        sql = ("SELECT s.id, s.name, s.cls, s.parent_name, s.parent_phone, s.admission_date, s.monthly_fee, x.roll "
               "FROM students s LEFT JOIN student_extra x ON x.student_id=s.id WHERE s.monthly_fee > 0")
        args = []
        if q:
            like = "%" + q.replace("%", "").replace("_", "") + "%"
            sql += " AND (s.name LIKE ? OR x.roll LIKE ? OR s.parent_phone LIKE ?)"
            args += [like, like, like]
        if cls:
            sql += " AND s.cls=?"
            args.append(cls)
        if bid:
            sql += " AND s.id IN (SELECT student_id FROM student_batches WHERE batch_id=?)"
            args.append(bid)
        return db().execute(sql + " ORDER BY s.name COLLATE NOCASE", args).fetchall()

    def pay_maps():
        pm, pid, pon = {}, {}, {}
        for r in db().execute("SELECT student_id sid, month, SUM(amount) amt, MAX(id) pid, MAX(paid_on) po FROM payments GROUP BY student_id, month"):
            pm.setdefault(r["sid"], {})[r["month"]] = r["amt"]
            pid[(r["sid"], r["month"])] = r["pid"]
            pon[(r["sid"], r["month"])] = r["po"]
        return pm, pid, pon

    def batch_list():
        return [dict(id=b["id"], name=b["name"]) for b in db().execute("SELECT id, name FROM batches ORDER BY name COLLATE NOCASE")]

    @app.route("/fees")
    def fees_home():
        lang, today = lang_of(), date.today()
        q = request.args.get("q", "").strip()[:40]
        flt = request.args.get("f", "")
        flt = flt if flt in ("upcoming", "pending", "paid") else ""
        cls = to_int(request.args.get("cls"))
        cls = cls if cls in (9, 10, 11, 12) else None
        bid = to_int(request.args.get("batch"))
        pm, pid, pon = pay_maps()
        mcol = {r[0]: r[1] for r in db().execute(
            "SELECT student_id, SUM(amount) FROM payments WHERE paid_on>=? AND paid_on<=? GROUP BY student_id",
            (today.replace(day=1).isoformat(), today.isoformat()))}
        cards, X, owed_total = [], 0, 0
        for s in filtered(q, cls, bid):
            sid, fee = s["id"], s["monthly_fee"] or 0
            a0, _x = sched(db, sid, s["admission_date"])
            hist = fee_history_s(db, sid, s["admission_date"], fee, pm.get(sid, {}), today)
            ents = []
            for h in hist:
                ny, nm = (h["y"] + 1, 1) if h["m"] == 12 else (h["y"], h["m"] + 1)
                po = parse_d(pon.get((sid, h["key"])))
                ents.append(dict(key=h["key"], st=h["st"], label=f"{MONTHS[lang][h['m'] - 1]} {h['y']}",
                    span=f"{sdm(lang, h['due'])} – {sdm(lang, due_date(a0, ny, nm))}",
                    amt=fee if h["st"] == "paid" else h["baaki"], pid=pid.get((sid, h["key"])) or "",
                    paid=sdm(lang, po) if po and h["st"] == "paid" else ""))
            due = [h for h in hist if h["st"] == "due"]
            soon = [h for h in hist if h["st"] == "soon"]
            owed = sum(h["baaki"] for h in due)
            wa = ""
            if due:
                st, kd, amt = "pending", due[0]["due"], owed
                info = dict(k="due_on" if len(due) == 1 else "months_since", d=sdm(lang, due[0]["due"]), n=len(due))
                if s["parent_phone"]:
                    wa = wa_link(s, due[0]["baaki"], due[0]["due"], due[0]["y"], due[0]["m"], lang)
            elif soon:
                st, kd, amt = "upcoming", soon[0]["due"], soon[0]["baaki"]
                info = dict(k="due_on", d=sdm(lang, soon[0]["due"]), n=1)
            elif hist:
                st, kd, amt = "paid", date.max, 0
                info = dict(k="paid_through", d=MONTHS[lang][hist[-1]["m"] - 1], n=0)
            else:
                a0d = parse_d(a0)
                st, kd, amt = "upcoming", a0d or date.max, fee
                info = dict(k="due_on" if a0d else "no_entries", d=sdm(lang, a0d) if a0d else "", n=1)
            X += mcol.get(sid, 0)
            owed_total += owed
            if flt and st != flt:
                continue
            cards.append(dict(id=sid, name=s["name"], roll=s["roll"] or "", st=st, kd=kd, amt=amt,
                              info=info, wa=wa, fee=fee, ents=ents[::-1]))
        cards.sort(key=lambda c: ({"pending": 0, "upcoming": 1, "paid": 2}[c["st"]], c["kd"], c["name"].lower()))
        Y = X + owed_total
        bl = batch_list()
        bname = next((b["name"] for b in bl if b["id"] == bid), "")

        def href(**over):
            p = dict(f=flt, q=q, cls=cls or "", batch=bid or "")
            p.update(over)
            return "/fees?" + urlencode({k: v for k, v in p.items() if v not in ("", None)})

        return render_template("fees.html", cards=cards, q=q, flt=flt, cls=cls, bid=bid, batches=bl,
            bname=bname, href=href, X=X, Y=Y, pct=round(100 * X / Y) if Y else 100,
            owed_total=owed_total, kf=kf, here=href())

    @app.route("/fees/collect", methods=["POST"])
    def fees_collect():
        sid = to_int(request.form.get("sid"))
        month = request.form.get("month", "")
        mode = request.form.get("mode", "Cash")
        mode = mode if mode in ("Cash", "UPI", "Other") else "Cash"
        s = db().execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not s or not mkey_ok(month):
            abort(404)
        y, m = int(month[:4]), int(month[5:])
        today = date.today()
        a0, _x = sched(db, sid, s["admission_date"])
        if (y, m) > (today.year, today.month) or not eligible(a0, y, m):
            abort(404)
        paid = db().execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE student_id=? AND month=?", (sid, month)).fetchone()[0]
        left = (s["monthly_fee"] or 0) - paid
        if left > 0:
            db().execute("INSERT INTO payments(student_id,month,amount,paid_on,mode) VALUES(?,?,?,?,?)",
                         (sid, month, left, today.isoformat(), mode))
            db().commit()
        return redirect(safe_next(request.form.get("next", "")))

    @app.route("/fees/undo", methods=["POST"])
    def fees_undo():
        sid = to_int(request.form.get("sid"))
        month = request.form.get("month", "")
        if sid is None or not mkey_ok(month):
            abort(404)
        db().execute("DELETE FROM payments WHERE student_id=? AND month=?", (sid, month))
        db().commit()
        return redirect(safe_next(request.form.get("next", "")))

    @app.route("/fees/collections")
    def fee_collections():
        lang, today = lang_of(), date.today()
        rk = request.args.get("r", "month")
        rk = rk if rk in ("today", "week", "month") else "month"
        mv = request.args.get("m", "")
        y, m = today.year, today.month
        if mkey_ok(mv) and 2000 <= int(mv[:4]) <= today.year:
            y, m = int(mv[:4]), int(mv[5:])
        if (y, m) > (today.year, today.month):
            y, m = today.year, today.month
        bid = to_int(request.args.get("batch"))
        bsql, bargs = "", []
        if bid:
            bsql = " AND p.student_id IN (SELECT student_id FROM student_batches WHERE batch_id=?)"
            bargs = [bid]
        first, last = date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])
        byday = {}
        for r in db().execute("SELECT p.paid_on d, SUM(p.amount) a FROM payments p WHERE p.paid_on BETWEEN ? AND ?" + bsql + " GROUP BY p.paid_on",
                              [first.isoformat(), last.isoformat()] + bargs):
            d = parse_d(r["d"])
            if d:
                byday[d.day] = r["a"]
        mx = max(byday.values()) if byday else 0
        dsel = parse_d(request.args.get("day", ""))
        if dsel and not (first <= dsel <= last):
            dsel = None
        if dsel:
            lo = hi = dsel
        elif rk == "today":
            lo = hi = today
        elif rk == "week":
            lo, hi = today - timedelta(days=today.weekday()), today
        else:
            lo, hi = first, last
        rows = db().execute("""SELECT p.student_id sid, p.amount, p.paid_on, COALESCE(p.mode,'Cash') mode, a.name
            FROM payments p LEFT JOIN (SELECT id, name FROM students UNION SELECT id, name FROM records) a ON a.id=p.student_id
            WHERE p.paid_on BETWEEN ? AND ?""" + bsql + " ORDER BY p.paid_on DESC, p.id DESC",
            [lo.isoformat(), hi.isoformat()] + bargs).fetchall()
        items = []
        for r in rows:
            d = parse_d(r["paid_on"])
            items.append(dict(sid=r["sid"], name=r["name"] or "—", amt=r["amount"], mode=r["mode"].upper(),
                              on=sdm(lang, d) if d else ""))
        sids = {r[0] for r in db().execute("SELECT student_id FROM student_batches WHERE batch_id=?", (bid,))} if bid else None
        pend = sum(v for k, v in owed_map(db).items() if sids is None or k in sids)
        weeks = []
        for w in calendar.Calendar(6).monthdayscalendar(y, m):
            row = []
            for d in w:
                if not d:
                    row.append(None)
                    continue
                a = byday.get(d, 0)
                rr = a / mx if mx else 0
                row.append(dict(d=d, a=a, k=kf(a), lv=0 if not a else (1 if rr <= .34 else (2 if rr <= .67 else 3)),
                                iso=date(y, m, d).isoformat(), today=(date(y, m, d) == today)))
            weeks.append(row)
        bd = max(byday, key=byday.get) if byday else None
        pv = (y - 1, 12) if m == 1 else (y, m - 1)
        nx = (y + 1, 1) if m == 12 else (y, m + 1)
        bl = batch_list()

        def href(**over):
            p = dict(r=rk, m=f"{y:04d}-{m:02d}", batch=bid or "", day="")
            p.update(over)
            return "/fees/collections?" + urlencode({k: v for k, v in p.items() if v not in ("", None)})

        return render_template("fee_collections.html", weeks=weeks, items=items, total=sum(i["amt"] for i in items),
            pend=pend, kf=kf, rk=rk, dsel=dsel, dtext=(f"{sdm(lang, dsel)} {dsel.year}" if dsel else ""),
            mtitle=f"{MONTHS[lang][m - 1]} {y}", wk=WEEK[lang], batches=bl, bid=bid,
            bname=next((b["name"] for b in bl if b["id"] == bid), ""), href=href,
            busiest=(f"{sdm(lang, date(y, m, bd))} · {kf(byday[bd])}" if bd else ""),
            prev=f"{pv[0]:04d}-{pv[1]:02d}", nxt=f"{nx[0]:04d}-{nx[1]:02d}",
            can_next=(y, m) < (today.year, today.month))
