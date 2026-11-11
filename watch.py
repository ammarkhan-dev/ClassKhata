"""ClassKhata - students absent for a week or more: red list + WhatsApp to parent."""
import sqlite3
from datetime import date, timedelta
from urllib.parse import quote
from flask import render_template, session
import store
import absent

LIMIT = 7

UI = {
    "en": dict(title="Long absent", sub="Not attended for a week or more", days="days",
               never="No present mark yet", wa="WhatsApp", nonum="No number",
               none="Nobody is absent for long. Great!", back="Alerts"),
    "hi": dict(title="लंबे समय से अनुपस्थित", sub="एक हफ़्ते या ज़्यादा से नहीं आए", days="दिन",
               never="अभी तक उपस्थित नहीं", wa="WhatsApp", nonum="नंबर नहीं",
               none="कोई लंबे समय से अनुपस्थित नहीं है। बहुत बढ़िया!", back="अलर्ट"),
}
MSG = {
    "en": "Dear {parent},\n\n{name} (Class {cls}) has not attended {inst} for {days} days.\n\n"
          "Please let us know if there is any problem. Regular attendance is important for good results.\n\n{sign}",
    "hi": "प्रिय {parent},\n\nआपके बच्चे {name} (कक्षा {cls}) पिछले {days} दिनों से {inst} में उपस्थित नहीं हुए हैं।\n\n"
          "यदि कोई समस्या हो तो कृपया हमें बताएँ। अच्छे परिणाम के लिए नियमित उपस्थिति ज़रूरी है।\n\n{sign}",
}


def long_absent(today=None):
    today = today or date.today()
    recent = (today - timedelta(days=LIMIT - 1)).isoformat()
    c = sqlite3.connect("classkhata.db")
    c.row_factory = sqlite3.Row
    rows = c.execute(
        "SELECT s.id, s.name, s.cls, s.parent_name, s.parent_phone, "
        "(SELECT MAX(day) FROM attendance WHERE student_id=s.id AND status='P') lastp, "
        "(SELECT MIN(day) FROM attendance WHERE student_id=s.id) firstd, "
        "(SELECT COUNT(*) FROM attendance WHERE student_id=s.id AND status='A' AND day>=?) a7 "
        "FROM students s ORDER BY s.cls, s.name COLLATE NOCASE", (recent,)).fetchall()
    c.close()
    out = []
    for r in rows:
        since = r["lastp"] or r["firstd"]
        if not since or r["a7"] < 1:
            continue
        try:
            n = (today - date.fromisoformat(since)).days
        except ValueError:
            continue
        if n >= LIMIT:
            out.append(dict(row=r, days=n, never=not r["lastp"]))
    out.sort(key=lambda x: -x["days"])
    return out


def alert_text(n):
    if absent._lang() == "hi":
        return "%d विद्यार्थी एक हफ़्ते से ज़्यादा समय से अनुपस्थित" % n
    return "%d student%s absent for over a week" % (n, "" if n == 1 else "s")


def _link(r, days, lg):
    ph = "".join(ch for ch in (r["parent_phone"] or "") if ch.isdigit())
    if len(ph) == 12 and ph.startswith("91"):
        ph = ph[2:]
    elif len(ph) == 11 and ph.startswith("0"):
        ph = ph[1:]
    if len(ph) != 10:
        return ""
    inst = store.get("institute", "") or "ClassKhata"
    sign = "\n".join(dict.fromkeys(x for x in (session.get("name", ""), inst) if x))
    parent = r["parent_name"] or ("Parent/Guardian" if lg == "en" else "अभिभावक")
    msg = MSG[lg].format(parent=parent, name=r["name"], cls=r["cls"], inst=inst, days=days, sign=sign)
    return "https://wa.me/91" + ph + "?text=" + quote(msg)


def setup(app, db=None):
    @app.route("/alerts/gayab")
    def long_absent_page():
        lg = absent._lang()
        items = []
        for x in long_absent():
            r = x["row"]
            items.append(dict(name=r["name"], cls=r["cls"], days=x["days"], never=x["never"],
                              url=_link(r, x["days"], lg)))
        return render_template("long_absent.html", L=UI[lg], items=items)
