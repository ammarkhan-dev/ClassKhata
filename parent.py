"""ClassKhata - read-only secret link for parents (attendance + fees).
Owner:  /students/<id>/parent   (login needed)      Parent:  /p/<token>   (no login)
"""
import calendar
import os
import re
import secrets
import sqlite3
from datetime import date, datetime
from urllib.parse import quote
from flask import Response, abort, redirect, render_template, request, session, url_for

import tenant

MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "hi": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
}
UI = {
    "en": dict(title="Parent link", sub="Attendance and fees, view only", link="Link", wa="Send on WhatsApp",
               copy="Copy link", copied="Copied", newl="Make a new link", newq="The old link will stop working. Continue?",
               info="Anyone with this link can see this student's attendance and fees, but cannot change anything. "
                    "Share it only with the parent.", back="Back", open="Open page",
               msg="Dear {parent},\n\nYou can see {name}'s attendance and fee status at {inst} here (view only):\n{url}\n\n{sign}"),
    "hi": dict(title="अभिभावक लिंक", sub="उपस्थिति और फ़ीस, केवल देखने के लिए", link="लिंक", wa="WhatsApp पर भेजें",
               copy="लिंक कॉपी करें", copied="कॉपी हो गया", newl="नया लिंक बनाएँ", newq="पुराना लिंक बंद हो जाएगा। आगे बढ़ें?",
               info="इस लिंक वाला कोई भी व्यक्ति इस विद्यार्थी की उपस्थिति और फ़ीस देख सकता है, पर कुछ बदल नहीं सकता। "
                    "इसे केवल अभिभावक को भेजें।", back="वापस", open="पेज खोलें",
               msg="आदरणीय {parent} जी,\n\n{inst} में {name} की उपस्थिति और फ़ीस की स्थिति आप यहाँ देख सकते हैं (केवल देखने के लिए):\n{url}\n\n{sign}"),
}
PUB = {
    "en": dict(att="Attendance", fees="Fees", present="Present", absent="Absent", holiday="Holiday", pct="Attendance",
               abs_days="Absent on", none_att="No attendance marked this month.", pending="Pending fee",
               allpaid="All fees are paid. Thank you!", paid="Paid", due="Due", soon="Upcoming", cls="Class",
               pay="How to pay", note="This page is view only.", other="हिन्दी", updated="Updated"),
    "hi": dict(att="उपस्थिति", fees="फ़ीस", present="उपस्थित", absent="अनुपस्थित", holiday="अवकाश", pct="उपस्थिति",
               abs_days="अनुपस्थित तिथियाँ", none_att="इस माह की उपस्थिति अभी नहीं लगी।", pending="बकाया फ़ीस",
               allpaid="सारी फ़ीस जमा है। धन्यवाद!", paid="जमा", due="बकाया", soon="आगामी", cls="कक्षा",
               pay="भुगतान कैसे करें", note="यह पेज केवल देखने के लिए है।", other="English", updated="अद्यतन"),
}


def _lg(v, default="hi"):
    return v if v in ("en", "hi") else default


def _setting(c, k, d=""):
    try:
        r = c.execute("SELECT v FROM settings WHERE k=?", (k,)).fetchone()
        return r[0] if r and r[0] is not None else d
    except sqlite3.Error:
        return d


def _ensure(c):
    c.execute("CREATE TABLE IF NOT EXISTS parent_links(student_id INTEGER PRIMARY KEY, token TEXT UNIQUE, created TEXT)")


def _owner_con():
    c = sqlite3.connect("classkhata.db")
    c.row_factory = sqlite3.Row
    _ensure(c)
    return c


def _fmt(d, lg):
    return "%d %s %d" % (d.day, MONTHS[lg][d.month - 1], d.year)


def _token_for(c, sid, new=False):
    r = c.execute("SELECT token FROM parent_links WHERE student_id=?", (sid,)).fetchone()
    if r and not new:
        return r["token"]
    tid = int(session.get("tid") or session.get("uid") or 0)
    tok = "%dx%s" % (tid, secrets.token_hex(10))
    c.execute("INSERT OR REPLACE INTO parent_links(student_id, token, created) VALUES(?,?,?)",
              (sid, tok, datetime.now().strftime("%Y-%m-%d %H:%M")))
    c.commit()
    return tok


def _public(token):
    m = re.fullmatch(r"(\d{1,9})x([0-9a-f]{20})", token or "")
    if not m:
        abort(404)
    path = tenant.path_for(int(m.group(1)))
    if not os.path.exists(path):
        abort(404)
    c = tenant.raw_connect(path)
    c.row_factory = sqlite3.Row
    try:
        r = c.execute("SELECT student_id FROM parent_links WHERE token=?", (token,)).fetchone()
    except sqlite3.Error:
        r = None
    if not r:
        c.close()
        abort(404)
    sid = r["student_id"]
    s = c.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    if not s:
        c.close()
        abort(404)
    lg = _lg(request.args.get("l"), _lg(_setting(c, "remind_lang"), "hi"))
    L = PUB[lg]
    today = date.today()
    mm = request.args.get("m", "")
    if re.fullmatch(r"\d{4}-\d{2}", mm) and 1 <= int(mm[5:]) <= 12 and 2000 <= int(mm[:4]) <= 2100:
        y, mo = int(mm[:4]), int(mm[5:])
    else:
        y, mo = today.year, today.month
    pv = (y - 1, 12) if mo == 1 else (y, mo - 1)
    nx = (y + 1, 1) if mo == 12 else (y, mo + 1)
    last = calendar.monthrange(y, mo)[1]
    rows = c.execute("SELECT day, status FROM attendance WHERE student_id=? AND day>=? AND day<=? ORDER BY day",
                     (sid, "%04d-%02d-01" % (y, mo), "%04d-%02d-%02d" % (y, mo, last))).fetchall()
    cnt = {"P": 0, "A": 0, "H": 0}
    absent_days = []
    for r in rows:
        if r["status"] in cnt:
            cnt[r["status"]] += 1
        if r["status"] == "A":
            absent_days.append(int(r["day"][8:10]))
    tot = cnt["P"] + cnt["A"]
    pct = round(100 * cnt["P"] / tot) if tot else None
    hist, owed = [], 0
    try:
        import fees
        pm = {r["month"]: r["amt"] for r in c.execute(
            "SELECT month, SUM(amount) amt FROM payments WHERE student_id=? GROUP BY month", (sid,))}
        h = fees.fee_history_s(lambda: c, sid, s["admission_date"], s["monthly_fee"], pm, today) if s["monthly_fee"] else []
        owed = sum(x["baaki"] for x in h if x["st"] == "due")
        for x in list(h)[-12:][::-1]:
            hist.append(dict(label=(x.get("label") or "%s %d" % (MONTHS[lg][x["m"] - 1], x["y"])), st=x["st"], baaki=x["baaki"], paid=x["paid"]))
    except Exception:
        hist = []
    inst = _setting(c, "institute", "")
    payinfo = _setting(c, "pay_info", "").strip()
    c.close()
    html = render_template("parent_view.html", L=L, lang=lg, other="en" if lg == "hi" else "hi", s=s, inst=inst,
                           label="%s %d" % (MONTHS[lg][mo - 1], y), cnt=cnt, pct=pct, absent_days=absent_days,
                           marked=bool(rows), hist=hist, owed=owed, payinfo=payinfo, token=token,
                           pv="%04d-%02d" % pv, nx="%04d-%02d" % nx, can_next=(y, mo) < (today.year, today.month),
                           today=_fmt(today, lg))
    resp = Response(html, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


def setup(app, db=None):
    def _pub():
        p = request.path
        if p.startswith("/p/") and "/" not in p[3:].strip("/"):
            return _public(p[3:].strip("/"))
        return None
    app.before_request_funcs.setdefault(None, []).insert(0, _pub)

    @app.route("/students/<int:sid>/parent", methods=["GET", "POST"])
    def parent_link(sid):
        lg = "hi" if session.get("lang") == "hi" else "en"
        L = UI[lg]
        c = _owner_con()
        s = c.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        if not s:
            c.close()
            abort(404)
        tok = _token_for(c, sid, new=(request.method == "POST"))
        inst = ""
        try:
            import store
            inst = store.get("institute", "") or ""
        except Exception:
            pass
        c.close()
        url = request.host_url.rstrip("/") + "/p/" + tok
        if request.is_secure is False and request.headers.get("X-Forwarded-Proto") == "https":
            url = url.replace("http://", "https://", 1)
        parent = s["parent_name"] or ("Parent/Guardian" if lg == "en" else "अभिभावक")
        sign = "\n".join(dict.fromkeys(x for x in (session.get("name", ""), inst) if x))
        msg = L["msg"].format(parent=parent, name=s["name"], inst=inst or "ClassKhata", url=url, sign=sign)
        ph = "".join(ch for ch in (s["parent_phone"] or "") if ch.isdigit())
        if len(ph) == 12 and ph.startswith("91"):
            ph = ph[2:]
        elif len(ph) == 11 and ph.startswith("0"):
            ph = ph[1:]
        wa = "https://wa.me/%s?text=%s" % (("91" + ph) if len(ph) == 10 else "", quote(msg))
        return render_template("parent_link.html", L=L, s=s, url=url, wa=wa)
