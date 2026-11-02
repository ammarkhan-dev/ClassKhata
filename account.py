"""ClassKhata - change password, recovery code, forgot password."""
import re, secrets, sqlite3, time
from flask import render_template, request, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
import tenant

DB = "classkhata.db"
ALPHA = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
MAX_FAILS = 5
LOCK_SECS = 15 * 60

UI = {
    "en": dict(title="Account", change="Change password", old="Current password", new="New password", new2="Confirm new password",
               save="Save", err_old="Current password is wrong", err_short="Password must be at least 6 characters",
               err_match="Passwords do not match", ok_pw="Password changed",
               rec="Recovery code", rec_info="If you forget your password, this code lets you set a new one. Keep it safe. It is shown only once.",
               st_set="A recovery code is set", st_none="No recovery code yet", mk="Make a new recovery code",
               warn="Making a new code stops the old one from working.", your="Your recovery code",
               save_now="Write it down or take a screenshot now. It will not be shown again.", done="I have saved it",
               f_title="Reset password", f_name="User name", f_code="Recovery code", f_btn="Reset password",
               err_f="Name or recovery code is wrong", err_lock="Too many wrong tries. Try again after 15 minutes.",
               f_help="No code? Ask the person who set up your app to reset your password.", back="Back to login", user="User"),
    "hi": dict(title="खाता", change="पासवर्ड बदलें", old="अभी का पासवर्ड", new="नया पासवर्ड", new2="नया पासवर्ड दोबारा लिखें",
               save="सेव करें", err_old="अभी का पासवर्ड गलत है", err_short="पासवर्ड कम से कम 6 अक्षर का हो",
               err_match="दोनों पासवर्ड एक जैसे नहीं हैं", ok_pw="पासवर्ड बदल गया",
               rec="रिकवरी कोड", rec_info="पासवर्ड भूलने पर इसी कोड से नया पासवर्ड बनेगा। इसे सुरक्षित रखें। ये सिर्फ एक बार दिखता है।",
               st_set="रिकवरी कोड बना हुआ है", st_none="अभी रिकवरी कोड नहीं बना है", mk="नया रिकवरी कोड बनाएँ",
               warn="नया कोड बनाने पर पुराना कोड बंद हो जाएगा।", your="आपका रिकवरी कोड",
               save_now="इसे अभी लिख लें या स्क्रीनशॉट ले लें। ये दोबारा नहीं दिखेगा।", done="मैंने सेव कर लिया",
               f_title="पासवर्ड रीसेट करें", f_name="यूज़र नाम", f_code="रिकवरी कोड", f_btn="पासवर्ड रीसेट करें",
               err_f="नाम या रिकवरी कोड गलत है", err_lock="बहुत ज़्यादा गलत कोशिशें। 15 मिनट बाद फिर कोशिश करें।",
               f_help="कोड नहीं है? जिसने आपका ऐप लगाया है उससे पासवर्ड रीसेट करवाएँ।", back="लॉगिन पर वापस", user="यूज़र"),
}


def _lg():
    return "hi" if session.get("lang") == "hi" else "en"


def _q(sql, args=(), one=False, commit=False):
    c = tenant.raw_connect(DB)
    c.row_factory = sqlite3.Row
    cur = c.execute(sql, args)
    if commit:
        c.commit()
    r = cur.fetchone() if one else cur.fetchall()
    c.close()
    return r


def _norm(code):
    return re.sub(r"[^A-Z0-9]", "", (code or "").upper())


def _new_code():
    return "-".join("".join(secrets.choice(ALPHA) for _ in range(4)) for _ in range(4))


def _ensure_columns():
    cols = [r["name"] for r in _q("PRAGMA table_info(users)")]
    if not cols:
        return
    for name, ddl in (("rec_hash", "TEXT"), ("rec_fails", "INTEGER DEFAULT 0"), ("rec_until", "REAL DEFAULT 0")):
        if name not in cols:
            _q("ALTER TABLE users ADD COLUMN %s %s" % (name, ddl), commit=True)


def setup(app, db=None):
    _ensure_columns()

    @app.route("/account", methods=["GET", "POST"])
    def account():
        lg = _lg()
        L = UI[lg]
        u = _q("SELECT * FROM users WHERE id=?", (session["uid"],), one=True)
        err = ok = None
        if request.method == "POST":
            old, new, new2 = request.form.get("old", ""), request.form.get("new", ""), request.form.get("new2", "")
            if not check_password_hash(u["pw_hash"], old):
                time.sleep(1)
                err = L["err_old"]
            elif len(new) < 6:
                err = L["err_short"]
            elif new != new2:
                err = L["err_match"]
            else:
                _q("UPDATE users SET pw_hash=? WHERE id=?", (generate_password_hash(new), u["id"]), commit=True)
                ok = L["ok_pw"]
        return render_template("account.html", L=L, lang=lg, err=err, ok=ok, has_code=bool(u["rec_hash"]), uname=u["name"])

    @app.route("/account/recovery", methods=["GET", "POST"])
    def account_recovery():
        lg = _lg()
        L = UI[lg]
        make = request.method == "POST" or session.pop("rec_pending", False)
        if make:
            code = _new_code()
            _q("UPDATE users SET rec_hash=?, rec_fails=0, rec_until=0 WHERE id=?",
               (generate_password_hash(_norm(code)), session["uid"]), commit=True)
            return render_template("recovery_show.html", L=L, lang=lg, code=code)
        return redirect("/account")

    @app.route("/forgot", methods=["GET", "POST"])
    def forgot():
        lg = _lg()
        L = UI[lg]
        err = None
        name = ""
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            code = _norm(request.form.get("code", ""))
            pw, pw2 = request.form.get("pw", ""), request.form.get("pw2", "")
            u = _q("SELECT * FROM users WHERE name=?", (name,), one=True) if name else None
            now = time.time()
            if u and (u["rec_until"] or 0) > now:
                err = L["err_lock"]
            elif len(pw) < 6:
                err = L["err_short"]
            elif pw != pw2:
                err = L["err_match"]
            elif u and u["rec_hash"] and code and check_password_hash(u["rec_hash"], code):
                _q("UPDATE users SET pw_hash=?, rec_fails=0, rec_until=0 WHERE id=?",
                   (generate_password_hash(pw), u["id"]), commit=True)
                session.permanent = True
                session.update(uid=u["id"], name=u["name"], lang=u["lang"] or lg, tid=u["id"], rec_pending=True)
                return redirect("/account/recovery")
            else:
                time.sleep(1)
                err = L["err_f"]
                if u:
                    fails = (u["rec_fails"] or 0) + 1
                    until = now + LOCK_SECS if fails >= MAX_FAILS else 0
                    _q("UPDATE users SET rec_fails=?, rec_until=? WHERE id=?",
                       (0 if until else fails, until, u["id"]), commit=True)
        return render_template("forgot.html", L=L, lang=lg, err=err, name=name)
