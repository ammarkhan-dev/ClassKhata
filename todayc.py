"""BatchBook - 'Aaj ki classes' card on Home, built from the batches' days and times.
Adds one helper  today_classes()  to every template; nothing else in the app changes."""
import sqlite3
from datetime import datetime
from flask import session

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_NAMES = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "hi": ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"],
}
MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "hi": ["जन॰", "फ़र॰", "मार्च", "अप्रैल", "मई", "जून", "जुला॰", "अग॰", "सित॰", "अक्टू॰", "नव॰", "दिस॰"],
}
UI = {
    "en": dict(title="Today's classes", now="Running now", done="Done", next="Next", none="No class today", stu="students", all="All batches",
               time="Time not set"),
    "hi": dict(title="आज की कक्षाएँ", now="अभी चल रही है", done="हो चुकी", next="आगे", none="आज कोई कक्षा नहीं", stu="विद्यार्थी", all="सभी बैच",
               time="समय तय नहीं"),
}


def _t12(s):
    try:
        h, m = int(s[:2]), int(s[3:5])
    except (ValueError, TypeError):
        return ""
    return "%d:%02d %s" % ((h % 12) or 12, m, "AM" if h < 12 else "PM")


def compute(now=None):
    lg = "hi" if session.get("lang") == "hi" else "en"
    L = UI[lg]
    now = now or datetime.now()
    day = DAYS[now.weekday()]
    hm = now.strftime("%H:%M")
    out = dict(has=False, L=L, title=L["title"], date="%s, %d %s" % (DAY_NAMES[lg][now.weekday()], now.day, MONTHS[lg][now.month - 1]), items=[])
    try:
        c = sqlite3.connect("classkhata.db")
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT * FROM batches ORDER BY CASE WHEN t_from IS NULL OR t_from='' THEN 1 ELSE 0 END, t_from, name COLLATE NOCASE").fetchall()
        if not rows:
            c.close()
            return out
        out["has"] = True
        for r in rows:
            if day not in (r["days"] or "").split(","):
                continue
            n = c.execute("SELECT COUNT(*) FROM student_batches sb JOIN students s ON s.id=sb.student_id WHERE sb.batch_id=?", (r["id"],)).fetchone()[0]
            a, b = r["t_from"] or "", r["t_to"] or ""
            if a and b:
                st = "now" if a <= hm <= b else ("done" if hm > b else "next")
                when = "%s – %s" % (_t12(a), _t12(b))
            else:
                st, when = "next", L["time"]
            out["items"].append(dict(name=r["name"], when=when, n=n, st=st, label=L[st]))
        c.close()
    except sqlite3.Error:
        out["has"] = False
    return out


def setup(app, db=None):
    @app.context_processor
    def _inject():
        return dict(today_classes=compute)
