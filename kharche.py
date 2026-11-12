"""BatchBook - coaching expenses + monthly profit (for a single-teacher coaching).
Collected money = payments (paid_on).  Profit = collected - coaching expenses.
'Apne liye nikala' (own withdrawal) is kept apart so it never reduces the coaching profit."""
import re
import sqlite3
from datetime import date
from flask import abort, redirect, render_template, request, session

CATS = [  # key, en, hi, colour
    ("rent", "Rent", "किराया", "#6366f1"),
    ("power", "Electricity / Water", "बिजली / पानी", "#f59e0b"),
    ("net", "Internet / Phone", "इंटरनेट / फ़ोन", "#06b6d4"),
    ("print", "Copy, Printing, Stationery", "कॉपी, प्रिंट, स्टेशनरी", "#10b981"),
    ("books", "Books / Study material", "किताबें / अध्ययन सामग्री", "#84cc16"),
    ("ads", "Advertising (pamphlet, banner)", "प्रचार (पर्चा, बैनर)", "#ec4899"),
    ("furn", "Furniture, Board, Equipment", "फ़र्नीचर, बोर्ड, उपकरण", "#8b5cf6"),
    ("repair", "Repair / Maintenance", "मरम्मत / रखरखाव", "#f97316"),
    ("travel", "Travel", "यात्रा", "#14b8a6"),
    ("food", "Tea, Snacks, Water", "चाय, नाश्ता, पानी", "#eab308"),
    ("soft", "Apps / Software / Subscriptions", "ऐप / सॉफ़्टवेयर / सदस्यता", "#3b82f6"),
    ("other", "Other", "अन्य", "#64748b"),
    ("self", "Taken for myself (not a coaching cost)", "अपने लिए निकाला (कोचिंग का ख़र्च नहीं)", "#94a3b8"),
]
KEYS = [c[0] for c in CATS]
UI = {
    "en": dict(title="Expenses", sub="Spending and monthly profit", coll="Fees collected", exp="Coaching expenses", profit="Profit",
               loss="Loss", last="Last month", more="more", less="less", self="Taken for myself", left="Left after that",
               add="Add expense", amount="Amount (₹)", cat="Category", day="Date", note="Note (optional)", save="Save",
               bycat="Where the money went", entries="Entries", none="No expense this month.", del_="Delete", back="Back",
               q="Delete this entry?", noexp="Nothing spent yet", tip="Profit = fees collected − coaching expenses.",
               same="same as last month"),
    "hi": dict(title="ख़र्चे", sub="ख़र्च और मासिक मुनाफ़ा", coll="जमा हुई फ़ीस", exp="कोचिंग के ख़र्च", profit="मुनाफ़ा",
               loss="घाटा", last="पिछला महीना", more="ज़्यादा", less="कम", self="अपने लिए निकाला", left="उसके बाद बचा",
               add="ख़र्च जोड़ें", amount="राशि (₹)", cat="श्रेणी", day="तारीख़", note="नोट (वैकल्पिक)", save="सेव करें",
               bycat="पैसा कहाँ गया", entries="प्रविष्टियाँ", none="इस महीने कोई ख़र्च नहीं।", del_="हटाएँ", back="वापस",
               q="यह प्रविष्टि हटाएँ?", noexp="अभी कुछ ख़र्च नहीं", tip="मुनाफ़ा = जमा फ़ीस − कोचिंग के ख़र्च।",
               same="पिछले महीने जितना"),
}
UI["hi"]["title"] = "ख़र्चे"
MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "hi": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
}
DDL = "CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT, amount INTEGER, cat TEXT, note TEXT)"


def _con():
    c = sqlite3.connect("classkhata.db")
    c.row_factory = sqlite3.Row
    c.execute(DDL)
    return c


def _month(v):
    if v and re.fullmatch(r"\d{4}-\d{2}", v) and 1 <= int(v[5:]) <= 12 and 2000 <= int(v[:4]) <= 2100:
        return int(v[:4]), int(v[5:])
    t = date.today()
    return t.year, t.month


def _span(y, m):
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return "%04d-%02d-01" % (y, m), "%04d-%02d-01" % (ny, nm)


def _totals(c, y, m):
    a, b = _span(y, m)
    try:
        coll = c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE paid_on>=? AND paid_on<?", (a, b)).fetchone()[0]
    except sqlite3.Error:
        coll = 0
    by = {r["cat"]: r["s"] for r in c.execute("SELECT cat, SUM(amount) s FROM expenses WHERE day>=? AND day<? GROUP BY cat", (a, b))}
    own = by.get("self", 0)
    exp = sum(v for k, v in by.items() if k != "self")
    return coll, exp, own, by


def setup(app, db=None):
    try:
        c = sqlite3.connect("classkhata.db"); c.execute(DDL); c.commit(); c.close()
    except sqlite3.Error:
        pass

    @app.route("/kharche", methods=["GET", "POST"])
    def kharche():
        lg = "hi" if session.get("lang") == "hi" else "en"
        L = UI[lg]
        y, m = _month(request.values.get("month"))
        mk = "%04d-%02d" % (y, m)
        c = _con()
        if request.method == "POST":
            cat = request.form.get("cat", "other")
            cat = cat if cat in KEYS else "other"
            try:
                amt = int(float(request.form.get("amount", "0") or 0))
                d = date.fromisoformat(request.form.get("day", "")).isoformat()
            except ValueError:
                amt, d = 0, ""
            if 0 < amt <= 100000000 and d:
                c.execute("INSERT INTO expenses(day,amount,cat,note) VALUES(?,?,?,?)", (d, amt, cat, request.form.get("note", "").strip()[:80]))
                c.commit()
                mk = d[:7]
            c.close()
            return redirect("/kharche?month=" + mk)
        coll, exp, own, by = _totals(c, y, m)
        py, pm_ = (y - 1, 12) if m == 1 else (y, m - 1)
        pcoll, pexp, _po, _pb = _totals(c, py, pm_)
        a, b = _span(y, m)
        rows = c.execute("SELECT * FROM expenses WHERE day>=? AND day<? ORDER BY day DESC, id DESC LIMIT 300", (a, b)).fetchall()
        c.close()
        names = {k: (en if lg == "en" else hi) for k, en, hi, _c in CATS}
        cols = {k: col for k, _e, _h, col in CATS}
        bars = []
        top = max([v for v in by.values()] + [1])
        for k in KEYS:
            if by.get(k):
                bars.append(dict(name=names[k], amt=by[k], w=max(4, round(100 * by[k] / top)), col=cols[k]))
        bars.sort(key=lambda x: -x["amt"])
        profit = coll - exp
        pprofit = pcoll - pexp
        nx = (y + 1, 1) if m == 12 else (y, m + 1)
        today = date.today()
        dflt = today.isoformat() if (y, m) == (today.year, today.month) else "%04d-%02d-01" % (y, m)
        return render_template("kharche.html", L=L, lg=lg, label="%s %d" % (MONTHS[lg][m - 1], y), mk=mk,
                               prev="%04d-%02d" % (py, pm_), nxt="%04d-%02d" % nx, can_next=(y, m) < (today.year, today.month),
                               coll=coll, exp=exp, own=own, profit=profit, left=profit - own, pprofit=pprofit,
                               diff=profit - pprofit, bars=bars, rows=rows, names=names, cols=cols,
                               cats=[(k, names[k]) for k in KEYS], dflt=dflt)

    @app.route("/kharche/<int:eid>/delete", methods=["POST"])
    def kharche_delete(eid):
        c = _con()
        r = c.execute("SELECT day FROM expenses WHERE id=?", (eid,)).fetchone()
        if not r:
            c.close(); abort(404)
        c.execute("DELETE FROM expenses WHERE id=?", (eid,)); c.commit(); c.close()
        return redirect("/kharche?month=" + r["day"][:7])
