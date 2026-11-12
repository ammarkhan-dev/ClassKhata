"""BatchBook - phone notifications (Web Push) + daily reminder job."""
import os, json, base64, secrets, sqlite3
from datetime import datetime
from flask import request, session, jsonify
import tenant
import store

HERE = os.path.dirname(os.path.abspath(__file__))
PRIV = os.path.join(HERE, ".vapid_private.pem")
CRON = os.path.join(HERE, ".cronkey")
_pub_cache = []

MSG = {
    "en": {
        "al_fees": ("Fees pending", "{n} student{s} · ₹{amt} left to collect", "/fees"),
        "al_late": ("Fees overdue", "{n} student{s} over a week late. Send a reminder to the parents.", "/alerts/fees"),
        "al_long": ("Long absence", "{n} student{s} absent for over a week. Check in with the parents.", "/alerts/gayab"),
        "al_att": ("Attendance pending", "Attendance is not marked for {n} class(es) today.", "/hazri"),
        "al_backup": ("Backup due", "Take a backup today to keep your data safe.", "/backup"),
        "al_end": ("Sessions ending", "{n} student{s} complete their session within 30 days.", "/records"),
    },
    "hi": {
        "al_fees": ("फ़ीस बाकी", "{n} विद्यार्थी · ₹{amt} वसूलना बाकी", "/fees"),
        "al_late": ("फ़ीस लेट", "{n} विद्यार्थियों की फ़ीस एक हफ़्ते से ज़्यादा लेट है। अभिभावकों को याद दिलाएँ।", "/alerts/fees"),
        "al_long": ("लंबी अनुपस्थिति", "{n} विद्यार्थी एक हफ़्ते से ज़्यादा अनुपस्थित हैं। अभिभावकों से बात करें।", "/alerts/gayab"),
        "al_att": ("हाज़िरी बाकी", "आज {n} क्लास की हाज़िरी नहीं लगी है।", "/hazri"),
        "al_backup": ("बैकअप का समय", "डेटा सुरक्षित रखने के लिए आज बैकअप ले लें।", "/backup"),
        "al_end": ("सत्र ख़त्म होने वाला", "{n} विद्यार्थियों का सत्र 30 दिन में पूरा होगा।", "/records"),
    },
}
PARTS = {"morning": ("al_fees", "al_late", "al_long", "al_backup", "al_end"), "att": ("al_att",)}


def _raw():
    c = tenant.raw_connect("classkhata.db")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS push_subs(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, "
              "endpoint TEXT UNIQUE, p256dh TEXT, auth TEXT, created TEXT)")
    return c


def _pub():
    if _pub_cache:
        return _pub_cache[0]
    try:
        from py_vapid import Vapid
        from cryptography.hazmat.primitives import serialization
        if not os.path.exists(PRIV):
            v = Vapid()
            v.generate_keys()
            v.save_key(PRIV)
        v = Vapid.from_file(PRIV)
        raw = v.public_key.public_bytes(serialization.Encoding.X962,
                                        serialization.PublicFormat.UncompressedPoint)
        k = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
        _pub_cache.append(k)
        return k
    except Exception:
        return ""


def _cronkey():
    if not os.path.exists(CRON):
        with open(CRON, "w") as f:
            f.write(secrets.token_urlsafe(24))
    with open(CRON) as f:
        return f.read().strip()


def send(uid, title, body, url, tag, host):
    try:
        from pywebpush import webpush, WebPushException
    except Exception:
        return 0
    _pub()
    c = _raw()
    rows = c.execute("SELECT * FROM push_subs WHERE uid=?", (uid,)).fetchall()
    ok = 0
    for r in rows:
        sub = {"endpoint": r["endpoint"], "keys": {"p256dh": r["p256dh"], "auth": r["auth"]}}
        try:
            webpush(sub, json.dumps({"title": title, "body": body, "url": url, "tag": tag}),
                    vapid_private_key=PRIV, vapid_claims={"sub": "https://" + host}, ttl=3600)
            ok += 1
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (404, 410):
                c.execute("DELETE FROM push_subs WHERE id=?", (r["id"],))
                c.commit()
        except Exception:
            pass
    c.close()
    return ok


def setup(app, db):
    @app.context_processor
    def _ctx():
        return dict(push_key=_pub)

    @app.route("/push/subscribe", methods=["POST"])
    def push_subscribe():
        j = request.get_json(silent=True) or {}
        k = j.get("keys") or {}
        ep, p, a = j.get("endpoint"), k.get("p256dh"), k.get("auth")
        if not (ep and p and a) or not str(ep).startswith("https://"):
            return jsonify(ok=False), 400
        c = _raw()
        c.execute("INSERT OR REPLACE INTO push_subs(uid, endpoint, p256dh, auth, created) VALUES(?,?,?,?,?)",
                  (session["uid"], ep, p, a, datetime.now().isoformat(timespec="seconds")))
        c.commit()
        c.close()
        return jsonify(ok=True)

    @app.route("/push/test", methods=["POST"])
    def push_test():
        hi = session.get("lang") == "hi"
        body = "फ़ीस, हाज़िरी और बैकअप के अलर्ट अब यहीं मिलेंगे।" if hi else "You will now get fee, attendance and backup alerts here."
        n = send(session["uid"], ("नोटिफ़िकेशन चालू हैं" if hi else "Notifications are on"), body, "/alerts", "test", request.host)
        return jsonify(sent=n)

    @app.route("/push/cron")
    def push_cron():
        if not secrets.compare_digest(request.args.get("key", ""), _cronkey()):
            return "no", 403
        part = request.args.get("part", "all")
        keys = PARTS.get(part) or (PARTS["morning"] + PARTS["att"])
        host = request.host
        import dash
        c = _raw()
        users = [dict(r) for r in c.execute("SELECT id, lang FROM users").fetchall()]
        have = {r[0] for r in c.execute("SELECT DISTINCT uid FROM push_subs").fetchall()}
        c.close()
        sent = 0
        for u in users:
            if u["id"] not in have:
                continue
            lg = u["lang"] if u["lang"] in ("en", "hi") else "en"
            with app.test_request_context("/"):
                session["tid"] = u["id"]
                session["uid"] = u["id"]
                session["lang"] = lg
                try:
                    items = dash.alert_list(db)
                except Exception:
                    continue
            for it in items:
                if it["key"] not in keys or it["key"] not in MSG[lg]:
                    continue
                title, body, url = MSG[lg][it["key"]]
                sent += send(u["id"], title, body.format(n=it.get("n", ""), amt=it.get("amt", ""), s="" if it.get("n") == 1 else "s"),
                             url, it["key"], host)
        return jsonify(ok=True, sent=sent)
