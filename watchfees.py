"""ClassKhata - fees more than a week late: red list + WhatsApp to parent."""
from datetime import date, timedelta
from flask import render_template
import fees
import absent

LIMIT = 7

UI = {
    "en": dict(title="Fees late", sub="Pending for a week or more", days="days late",
               wa="WhatsApp", nonum="No number", none="No late fees. Great!", back="Alerts"),
    "hi": dict(title="फ़ीस लेट", sub="एक हफ़्ते या ज़्यादा से बकाया", days="दिन लेट",
               wa="WhatsApp", nonum="नंबर नहीं", none="कोई फ़ीस लेट नहीं है। बहुत बढ़िया!", back="अलर्ट"),
}


def late_list(db):
    today = date.today()
    cut = today - timedelta(days=LIMIT)
    out = []
    rows = db().execute("SELECT id,name,cls,parent_name,parent_phone,admission_date,monthly_fee "
                        "FROM students WHERE monthly_fee > 0 ORDER BY cls, name COLLATE NOCASE").fetchall()
    for s in rows:
        pm = {r["month"]: r["amt"] for r in db().execute(
            "SELECT month, SUM(amount) amt FROM payments WHERE student_id=? GROUP BY month", (s["id"],))}
        hist = fees.fee_history_s(db, s["id"], s["admission_date"], s["monthly_fee"], pm, today)
        late = [h for h in hist if h.get("st") == "due" and h.get("baaki", 0) > 0
                and (h.get("due") is None or h["due"] <= cut)]
        if late:
            old = min(late, key=lambda h: h.get("due") or today)
            days = (today - old["due"]).days if old.get("due") else 0
            out.append(dict(row=s, amt=sum(h["baaki"] for h in late), old=old, days=days))
    out.sort(key=lambda x: -x["days"])
    return out


def alert_text(n):
    if absent._lang() == "hi":
        return "%d विद्यार्थियों की फ़ीस एक हफ़्ते से ज़्यादा लेट है" % n
    return "%d student%s with fees over a week late" % (n, "" if n == 1 else "s")


def setup(app, db):
    @app.route("/alerts/fees")
    def late_fees_page():
        lg = absent._lang()
        items = []
        for x in late_list(db):
            r, o = x["row"], x["old"]
            try:
                url = fees.wa_link(r, o["baaki"], o["due"], o["y"], o["m"], lg)
            except Exception:
                url = ""
            items.append(dict(name=r["name"], cls=r["cls"], amt=f"{x['amt']:,}", days=x["days"], url=url))
        return render_template("late_fees.html", L=UI[lg], items=items)
