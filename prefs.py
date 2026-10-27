import sqlite3
from flask import render_template, request, redirect, abort, session
from werkzeug.security import check_password_hash, generate_password_hash
import store
from auth import q as auth_q
from fees import owed_map, parse_d, fmt, MONTHS
from more import backup_info
from students import cur_session

DEF = dict(inst_addr="", inst_phone="", remind_lang="", pay_info="", rec_note="", def_mode="Cash",
           idc_color="navy", idc_phone="1", idc_father="1", idc_addr="0", idc_footer="", idc_sign="Principal")
COLORS = {"navy": "#222f40", "green": "#1f7a45", "maroon": "#8a2230", "teal": "#0f7b8a"}

def lang_of():
    l = session.get("lang", "en")
    return l if l in MONTHS else "en"

def cfg():
    c = sqlite3.connect("classkhata.db")
    c.execute("CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT)")
    got = dict(c.execute("SELECT k, v FROM settings").fetchall())
    c.close()
    return {k: got.get(k, d) for k, d in DEF.items()}

def setup(app, db):
    with sqlite3.connect("classkhata.db") as c:
        c.execute("CREATE TABLE IF NOT EXISTS fee_plans(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, amount INTEGER NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT)")

    @app.context_processor
    def prefs_ctx():
        c = cfg()
        con = sqlite3.connect("classkhata.db")
        plans = [dict(name=r[0], amount=r[1]) for r in con.execute("SELECT name, amount FROM fee_plans ORDER BY amount, name")]
        con.close()
        return dict(inst_addr=c["inst_addr"], inst_phone=c["inst_phone"], rec_note=c["rec_note"],
                    def_mode=c["def_mode"], fee_plans=plans)

    def card_data(s):
        if not s:
            return dict(id=0, name="Student Name", cls=12, roll="0001", phone="98765 43210", father="Father's Name",
                        addr="Village, District", valid="31 Mar 2027", ses="2026-27", photo=False)
        ex = db().execute("SELECT roll, address FROM student_extra WHERE student_id=?", (s["id"],)).fetchone()
        ph = db().execute("SELECT 1 FROM student_photo WHERE student_id=?", (s["id"],)).fetchone() is not None
        d = parse_d(s["session_end"])
        return dict(id=s["id"], name=s["name"], cls=s["cls"], roll=(ex["roll"] if ex and ex["roll"] else ""),
                    phone=s["parent_phone"] or "", father=s["parent_name"] or "",
                    addr=(ex["address"] if ex and ex["address"] else ""),
                    valid=fmt(d, lang_of()) if d else "", ses=s["acad_session"] or "", photo=ph)

    @app.route("/more")
    def more():
        c = cfg()
        n = lambda sql: db().execute(sql).fetchone()[0]
        last, due = backup_info()
        return render_template("settings_hub.html", due=due, nb=n("SELECT COUNT(*) FROM batches"),
            ns=n("SELECT COUNT(*) FROM students"), ncl=n("SELECT COUNT(DISTINCT cls) FROM students"),
            npl=n("SELECT COUNT(*) FROM fee_plans"), color=c["idc_color"])

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        saved = False
        if request.method == "POST":
            nm = request.form.get("inst", "").strip()[:80]
            if nm:
                store.put("institute", nm)
                store.put("inst_addr", request.form.get("addr", "").strip()[:160])
                ph = "".join(ch for ch in request.form.get("phone", "") if ch.isdigit() or ch in "+ -")[:20]
                store.put("inst_phone", ph.strip())
                saved = True
        return render_template("settings_inst.html", saved=saved, c=cfg())

    @app.route("/classes")
    def classes():
        owed = owed_map(db)
        rows = []
        for k in (9, 10, 11, 12):
            ids = [r["id"] for r in db().execute("SELECT id FROM students WHERE cls=?", (k,))]
            ex = db().execute("SELECT COALESCE(SUM(monthly_fee),0) FROM students WHERE cls=?", (k,)).fetchone()[0]
            rows.append(dict(cls=k, n=len(ids), exp=ex, pend=sum(owed.get(i, 0) for i in ids)))
        nrec = db().execute("SELECT COUNT(*) FROM records").fetchone()[0]
        return render_template("classes.html", rows=rows, ses=cur_session(), nrec=nrec)

    def plan_save(pid):
        f = request.form
        name = f.get("name", "").strip()[:40]
        try:
            amt = int(f.get("amount", ""))
        except ValueError:
            amt = -1
        if not name or not 0 < amt <= 1000000:
            return "err_plan"
        if pid is None:
            db().execute("INSERT INTO fee_plans(name, amount) VALUES(?,?)", (name, amt))
        else:
            db().execute("UPDATE fee_plans SET name=?, amount=? WHERE id=?", (name, amt, pid))
        db().commit()
        return None

    @app.route("/fee-plans")
    def fee_plans_page():
        return render_template("fee_plans.html", rows=db().execute("SELECT * FROM fee_plans ORDER BY amount, name").fetchall())

    @app.route("/fee-plans/new", methods=["GET", "POST"])
    def fee_plan_new():
        err = None
        if request.method == "POST":
            err = plan_save(None)
            if not err:
                return redirect("/fee-plans")
        return render_template("fee_plan_form.html", p=None, err=err)

    @app.route("/fee-plans/<int:pid>/edit", methods=["GET", "POST"])
    def fee_plan_edit(pid):
        p = db().execute("SELECT * FROM fee_plans WHERE id=?", (pid,)).fetchone()
        if not p:
            abort(404)
        err = None
        if request.method == "POST":
            err = plan_save(pid)
            if not err:
                return redirect("/fee-plans")
        return render_template("fee_plan_form.html", p=p, err=err)

    @app.route("/fee-plans/<int:pid>/delete", methods=["POST"])
    def fee_plan_delete(pid):
        db().execute("DELETE FROM fee_plans WHERE id=?", (pid,))
        db().commit()
        return redirect("/fee-plans")

    @app.route("/fee-settings", methods=["GET", "POST"])
    def fee_settings():
        saved = False
        if request.method == "POST":
            f = request.form
            rl = f.get("remind_lang", "")
            store.put("remind_lang", rl if rl in ("en", "hi") else "")
            dm = f.get("def_mode", "Cash")
            store.put("def_mode", dm if dm in ("Cash", "UPI", "Other") else "Cash")
            store.put("pay_info", f.get("pay_info", "").strip()[:200])
            store.put("rec_note", f.get("rec_note", "").strip()[:160])
            saved = True
        return render_template("fee_settings.html", saved=saved, c=cfg())

    @app.route("/idcard-settings", methods=["GET", "POST"])
    def idcard_settings():
        saved = False
        if request.method == "POST":
            f = request.form
            col = f.get("color", "navy")
            store.put("idc_color", col if col in COLORS else "navy")
            for k in ("phone", "father", "addr"):
                store.put("idc_" + k, "1" if f.get("show_" + k) else "0")
            store.put("idc_footer", f.get("footer", "").strip()[:80])
            store.put("idc_sign", f.get("sign", "").strip()[:30])
            saved = True
        s = db().execute("SELECT * FROM students ORDER BY id LIMIT 1").fetchone()
        return render_template("idcard_settings.html", saved=saved, c=cfg(), ic=card_data(s), COLORS=COLORS)

    @app.route("/students/<int:sid>/idcard")
    def idcard(sid):
        s = db().execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not s:
            abort(404)
        return render_template("idcard.html", s=s, c=cfg(), ic=card_data(s), COLORS=COLORS)

    @app.route("/app-settings")
    def app_settings():
        last, due = backup_info()
        err = request.args.get("err")
        err = err if err in ("err_pw_cur", "err_pw_short", "err_pw_match") else None
        return render_template("app_settings.html", last=last, due=due, err=err, ok=request.args.get("ok"))

    @app.route("/app-settings/password", methods=["POST"])
    def change_password():
        u = auth_q("SELECT * FROM users WHERE id=?", (session.get("uid"),), one=True)
        f = request.form
        if not u or not check_password_hash(u["pw_hash"], f.get("cur", "")):
            return redirect("/app-settings?err=err_pw_cur#pw")
        if len(f.get("new", "")) < 6:
            return redirect("/app-settings?err=err_pw_short#pw")
        if f.get("new") != f.get("new2"):
            return redirect("/app-settings?err=err_pw_match#pw")
        auth_q("UPDATE users SET pw_hash=? WHERE id=?", (generate_password_hash(f["new"]), u["id"]), commit=True)
        return redirect("/app-settings?ok=1#pw")
