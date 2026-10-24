import os, secrets, time, sqlite3
import store
from datetime import timedelta
from urllib.parse import urlparse
from flask import request, session, redirect, render_template
from werkzeug.security import generate_password_hash, check_password_hash

DB = "classkhata.db"

def q(sql, args=(), one=False, commit=False):
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    cur = c.execute(sql, args)
    if commit:
        c.commit()
    r = cur.fetchone() if one else cur.fetchall()
    c.close()
    return r

def setup(app):
    q("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE COLLATE NOCASE NOT NULL,
        pw_hash TEXT NOT NULL, lang TEXT DEFAULT 'en')""", commit=True)
    if not os.path.exists(".secret"):
        open(".secret", "w").write(secrets.token_hex(32))
    app.secret_key = open(".secret").read().strip()
    app.permanent_session_lifetime = timedelta(days=30)

    def no_users():
        return q("SELECT COUNT(*) n FROM users", one=True)["n"] == 0

    @app.context_processor
    def who():
        return dict(user_name=session.get("name"))

    @app.before_request
    def guard():
        if request.endpoint in ("login", "signup", "set_lang", "static"):
            return
        if not session.get("uid") or not q("SELECT 1 FROM users WHERE id=?", (session["uid"],), one=True):
            session.pop("uid", None)
            session.pop("name", None)
            return redirect("/signup" if no_users() else "/login")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if not no_users():
            return redirect("/login")
        err, name, inst = None, "", ""
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            pw = request.form.get("pw", "")
            lang = session.get("lang", "en")
            inst = request.form.get("inst", "").strip()[:80]
            if lang not in ("en", "hi"):
                lang = "en"
            if not name:
                err = "err_name"
            elif not inst:
                err = "err_inst"
            elif len(pw) < 6:
                err = "err_pw_short"
            elif pw != request.form.get("pw2", ""):
                err = "err_pw_match"
            else:
                q("INSERT INTO users(name,pw_hash,lang) VALUES(?,?,?)",
                  (name, generate_password_hash(pw), lang), commit=True)
                store.put("institute", inst)
                u = q("SELECT * FROM users WHERE name=?", (name,), one=True)
                session.permanent = True
                session.update(uid=u["id"], name=u["name"], lang=lang)
                return redirect("/")
        return render_template("signup.html", err=err, name=name, inst=inst)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if no_users():
            return redirect("/signup")
        err = None
        if request.method == "POST":
            u = q("SELECT * FROM users WHERE name=?",
                  (request.form.get("name", "").strip(),), one=True)
            if u and check_password_hash(u["pw_hash"], request.form.get("pw", "")):
                session.permanent = True
                session.update(uid=u["id"], name=u["name"], lang=u["lang"])
                return redirect("/")
            time.sleep(1)
            err = "err_login"
        return render_template("login.html", err=err)

    @app.route("/logout")
    def logout():
        lang = session.get("lang", "en")
        session.clear()
        session["lang"] = lang
        return redirect("/login")

    @app.route("/lang/<code>")
    def set_lang(code):
        if code in ("en", "hi"):
            session["lang"] = code
            if session.get("uid"):
                q("UPDATE users SET lang=? WHERE id=?", (code, session["uid"]), commit=True)
        p = urlparse(request.referrer or "")
        dest = (p.path or "/") + ("?" + p.query if p.query else "")
        if not dest.startswith("/") or dest.startswith("//"):
            dest = "/"
        return redirect(dest)
