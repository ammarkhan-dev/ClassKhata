"""ClassKhata - Notes / yaad-dilane wale notes. Date daalo to us din Home par card + phone notification (app khulne par)."""
import sqlite3
from datetime import datetime, timedelta
from flask import session, request, redirect, render_template

UI = {
 "en": dict(title="Notes & reminders", today="Today's notes", add="Add note", ph="Write note (e.g. ask Rahul about fees)", date="Remind on date (optional)",
            save="Save note", due="Due today / pending", soon="Coming up", nodate="No date", done="Done", none="No notes yet", all="All notes", new="+ New note",
            enable="Turn on notifications", mark="Done", dele="Delete", over="Overdue", back="Notes", shown="Today"),
 "hi": dict(title="नोट्स और याद-दिहानी", today="आज के नोट्स", add="नोट जोड़ें", ph="नोट लिखें (जैसे: राहुल से फ़ीस पूछनी है)", date="किस तारीख़ को याद दिलाएँ (ज़रूरी नहीं)",
            save="नोट सेव करें", due="आज / बाकी", soon="आने वाले", nodate="बिना तारीख़", done="हो गए", none="अभी कोई नोट नहीं", all="सारे नोट्स", new="+ नया नोट",
            enable="नोटिफ़िकेशन चालू करें", mark="हो गया", dele="हटाएँ", over="बीत चुका", back="नोट्स", shown="आज"),
}

def _today():
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()

def _lg():
    return "hi" if session.get("lang") == "hi" else "en"

def _db():
    c = sqlite3.connect("classkhata.db")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, remind_date TEXT, done INTEGER DEFAULT 0, created TEXT)")
    return c

def _fmt(d, lg):
    if not d:
        return ""
    try:
        x = datetime.strptime(d, "%Y-%m-%d")
    except ValueError:
        return d
    return x.strftime("%d-%m-%Y")

def due_notes():
    """Template helper: notes jinka din aa gaya (ya nikal gaya) aur jo baaki hain."""
    L = UI[_lg()]
    out = dict(has=False, L=L, items=[], js=[], today=_today().isoformat())
    try:
        c = _db()
        t = _today().isoformat()
        rows = c.execute("SELECT * FROM notes WHERE done=0 AND remind_date IS NOT NULL AND remind_date!='' AND remind_date<=? ORDER BY remind_date, id", (t,)).fetchall()
        c.commit(); c.close()
    except sqlite3.Error:
        return out
    for r in rows:
        out["items"].append(dict(id=r["id"], text=r["text"], date=_fmt(r["remind_date"], _lg()), late=r["remind_date"] < t))
        out["js"].append(dict(id=r["id"], text=r["text"]))
    out["has"] = bool(rows)
    return out

def setup(app, db=None):
    @app.context_processor
    def _inject():
        return dict(notes_today=due_notes)

    def guard():
        return None if session.get("tid") else redirect("/")

    def page():
        g = guard()
        if g: return g
        lg = _lg(); t = _today().isoformat()
        c = _db(); rows = c.execute("SELECT * FROM notes ORDER BY done, CASE WHEN remind_date IS NULL OR remind_date='' THEN 1 ELSE 0 END, remind_date, id DESC").fetchall(); c.commit(); c.close()
        grp = dict(due=[], soon=[], nodate=[], done=[])
        for r in rows:
            d = dict(id=r["id"], text=r["text"], date=_fmt(r["remind_date"], lg), late=bool(r["remind_date"]) and r["remind_date"] < t)
            if r["done"]: grp["done"].append(d)
            elif not r["remind_date"]: grp["nodate"].append(d)
            elif r["remind_date"] <= t: grp["due"].append(d)
            else: grp["soon"].append(d)
        return render_template("ntnotes.html", L=UI[lg], grp=grp, mindate=t)

    def add():
        g = guard()
        if g: return g
        txt = (request.form.get("text") or "").strip()[:500]
        d = (request.form.get("date") or "").strip()
        try:
            if d: datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            d = ""
        if txt:
            c = _db(); c.execute("INSERT INTO notes(text,remind_date,created) VALUES(?,?,?)", (txt, d or None, _today().isoformat())); c.commit(); c.close()
        return redirect("/notes")

    def done(i):
        g = guard()
        if g: return g
        c = _db(); c.execute("UPDATE notes SET done=1-done WHERE id=?", (i,)); c.commit(); c.close()
        return redirect(request.form.get("next") or "/notes")

    def dele(i):
        g = guard()
        if g: return g
        c = _db(); c.execute("DELETE FROM notes WHERE id=?", (i,)); c.commit(); c.close()
        return redirect("/notes")

    app.add_url_rule("/notes", "nt_page", page)
    app.add_url_rule("/notes/add", "nt_add", add, methods=["POST"])
    app.add_url_rule("/notes/<int:i>/done", "nt_done", done, methods=["POST"])
    app.add_url_rule("/notes/<int:i>/del", "nt_del", dele, methods=["POST"])
