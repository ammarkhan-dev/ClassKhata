"""ClassKhata - absent students -> one-tap WhatsApp message to the parent."""
import sqlite3
from datetime import date, datetime, timedelta
from urllib.parse import quote
from flask import render_template, request, session, jsonify
import store

MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "hi": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
}
MSG = {
    "en": "Dear {parent},\n\n{name} (Class {cls}) was absent {when} from {inst}.\n\n"
          "If there is any problem, please let us know. Regular attendance is important for good results.\n\n{sign}",
    "hi": "प्रिय {parent},\n\nआपके बच्चे {name} (कक्षा {cls}) {when} {inst} में अनुपस्थित रहे।\n\n"
          "यदि कोई समस्या हो तो कृपया हमें बताएँ। अच्छे परिणाम के लिए नियमित उपस्थिति ज़रूरी है।\n\n{sign}",
}
UI = {
    "en": dict(title="Absent today", sub="Message the parents", absent="Absent", unmarked="not marked yet", all="All",
               wa="WhatsApp", nonum="No number", sent="Sent", none="Nobody is absent. Great!", today="Today",
               hint="Tap WhatsApp. The message is ready, you only press send.", back="Attendance", prev="Previous day", next="Next day"),
    "hi": dict(title="आज अनुपस्थित", sub="अभिभावकों को संदेश", absent="अनुपस्थित", unmarked="की उपस्थिति अभी नहीं लगी", all="सभी",
               wa="WhatsApp", nonum="नंबर नहीं", sent="भेजा गया", none="कोई अनुपस्थित नहीं है। बहुत बढ़िया!", today="आज",
               hint="WhatsApp दबाएँ। संदेश तैयार मिलेगा, बस भेजना दबाना है।", back="हाज़िरी", prev="पिछला दिन", next="अगला दिन"),
}


def _lang():
    rl = store.get("remind_lang", "")
    if rl in ("en", "hi"):
        return rl
    return "hi" if session.get("lang") == "hi" else "en"


def _day(arg):
    try:
        return datetime.strptime(arg, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return date.today()


def _fmt(d, lg):
    return "%d %s %d" % (d.day, MONTHS[lg][d.month - 1], d.year)


def _con():
    c = sqlite3.connect("classkhata.db")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS absent_sent(student_id INTEGER, day TEXT, sent_at TEXT, PRIMARY KEY(student_id, day))")
    return c


def link(s, d, lg):
    ph = "".join(ch for ch in (s["parent_phone"] or "") if ch.isdigit())
    if len(ph) == 12 and ph.startswith("91"):
        ph = ph[2:]
    elif len(ph) == 11 and ph.startswith("0"):
        ph = ph[1:]
    if len(ph) != 10:
        return ""
    inst = store.get("institute", "") or "ClassKhata"
    sign = "\n".join(dict.fromkeys(x for x in (session.get("name", ""), inst) if x))
    parent = s["parent_name"] or ("Parent/Guardian" if lg == "en" else "अभिभावक")
    if lg == "en":
        when = ("today (%s)" if d == date.today() else "on %s") % _fmt(d, lg)
    else:
        when = ("आज (%s)" if d == date.today() else "%s") % _fmt(d, lg)
        when += " को"
    msg = MSG[lg].format(parent=parent, name=s["name"], cls=s["cls"], inst=inst, when=when, sign=sign)
    return "https://wa.me/91" + ph + "?text=" + quote(msg)


def setup(app, db=None):
    @app.route("/hazri/absent")
    def absent_list():
        lg = _lang()
        L = UI[lg]
        d = _day(request.args.get("d"))
        cls = request.args.get("cls", type=int)
        c = _con()
        q = ("SELECT s.*, a.status st FROM students s LEFT JOIN attendance a ON a.student_id=s.id AND a.day=? "
             "ORDER BY s.cls, s.name COLLATE NOCASE")
        rows = c.execute(q, (d.isoformat(),)).fetchall()
        sent = {r["student_id"]: r["sent_at"] for r in c.execute("SELECT * FROM absent_sent WHERE day=?", (d.isoformat(),))}
        c.close()
        classes = sorted({r["cls"] for r in rows})
        view = [r for r in rows if cls is None or r["cls"] == cls]
        items = [dict(id=r["id"], name=r["name"], cls=r["cls"], phone=r["parent_phone"] or "",
                      url=link(r, d, lg), sent=sent.get(r["id"])) for r in view if r["st"] == "A"]
        unmarked = sum(1 for r in view if r["st"] is None)
        return render_template("absent.html", L=L, lang=lg, d=d.isoformat(), dlabel=_fmt(d, lg), is_today=(d == date.today()),
                               prev=(d - timedelta(days=1)).isoformat(), nxt=(d + timedelta(days=1)).isoformat(),
                               items=items, unmarked=unmarked, classes=classes, cls=cls)

    @app.route("/hazri/absent/sent", methods=["POST"])
    def absent_sent():
        sid = request.form.get("sid", type=int)
        d = _day(request.form.get("d"))
        if sid:
            c = _con()
            c.execute("INSERT OR REPLACE INTO absent_sent(student_id, day, sent_at) VALUES(?,?,?)",
                      (sid, d.isoformat(), datetime.now().strftime("%H:%M")))
            c.commit(); c.close()
        return jsonify(ok=True)
