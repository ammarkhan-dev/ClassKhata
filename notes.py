"""BatchBook - Notes and date/time reminders."""
import sqlite3
from datetime import datetime, timedelta
from flask import session, request, redirect, render_template

UI = {
    "en": dict(
        title="Notes & reminders", today="Today's notes", add="Add note",
        ph="Write your reminder", date="Remind on date (optional)",
        time="Reminder time (optional)", save="Save note",
        due="Due / pending", soon="Coming up", nodate="No date",
        done="Done", none="No notes yet", all="All notes",
        new="+ New note", enable="Turn on notifications",
        mark="Done", dele="Delete", over="Overdue",
        back="Notes", shown="Today", at="At"
    ),
    "hi": dict(
        title="नोट्स और याद-दिहानी", today="आज के नोट्स",
        add="नोट जोड़ें", ph="अपना रिमाइंडर लिखें",
        date="किस तारीख़ को याद दिलाएँ (ज़रूरी नहीं)",
        time="किस समय याद दिलाएँ (ज़रूरी नहीं)",
        save="नोट सेव करें", due="बाकी / समय हो गया",
        soon="आने वाले", nodate="बिना तारीख़",
        done="हो गए", none="अभी कोई नोट नहीं",
        all="सारे नोट्स", new="+ नया नोट",
        enable="नोटिफ़िकेशन चालू करें", mark="हो गया",
        dele="हटाएँ", over="समय बीत चुका",
        back="नोट्स", shown="आज", at="समय"
    ),
}

def _now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def _today():
    return _now().date()

def _lg():
    return "hi" if session.get("lang") == "hi" else "en"

def _db():
    c = sqlite3.connect("classkhata.db")
    c.row_factory = sqlite3.Row
    c.execute("""
        CREATE TABLE IF NOT EXISTS notes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            remind_date TEXT,
            done INTEGER DEFAULT 0,
            created TEXT
        )
    """)
    cols = [r["name"] for r in c.execute("PRAGMA table_info(notes)").fetchall()]
    if "remind_time" not in cols:
        c.execute("ALTER TABLE notes ADD COLUMN remind_time TEXT")
    return c

def _fmt(d, lg):
    if not d:
        return ""
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        return d

def _is_due(date_value, time_value, now):
    if not date_value:
        return False
    if date_value < now.date().isoformat():
        return True
    if date_value > now.date().isoformat():
        return False
    if not time_value:
        return True
    try:
        return time_value <= now.strftime("%H:%M")
    except Exception:
        return True

def due_notes():
    L = UI[_lg()]
    out = dict(has=False, L=L, items=[], js=[], today=_today().isoformat())
    try:
        c = _db()
        now = _now()
        t = now.date().isoformat()
        rows = c.execute("""
            SELECT * FROM notes
            WHERE done=0 AND remind_date IS NOT NULL AND remind_date!=''
              AND remind_date<=?
            ORDER BY remind_date, remind_time, id
        """, (t,)).fetchall()
        c.commit()
        c.close()
    except sqlite3.Error:
        return out

    for r in rows:
        date_value = r["remind_date"]
        time_value = r["remind_time"] or ""
        out["js"].append(dict(
            id=r["id"], text=r["text"],
            date=date_value, time=time_value
        ))
        if _is_due(date_value, time_value, now):
            out["items"].append(dict(
                id=r["id"], text=r["text"],
                date=_fmt(date_value, _lg()),
                time=time_value,
                late=date_value < t
            ))
    out["has"] = bool(out["items"])
    return out

def setup(app, db=None):
    @app.context_processor
    def _inject():
        return dict(notes_today=due_notes)

    def guard():
        return None if session.get("tid") else redirect("/")

    def page():
        g = guard()
        if g:
            return g
        lg = _lg()
        t = _today().isoformat()
        c = _db()
        rows = c.execute("""
            SELECT * FROM notes
            ORDER BY done,
            CASE WHEN remind_date IS NULL OR remind_date='' THEN 1 ELSE 0 END,
            remind_date, remind_time, id DESC
        """).fetchall()
        c.close()

        now = _now()
        grp = dict(due=[], soon=[], nodate=[], done=[])
        for r in rows:
            d = r["remind_date"] or ""
            tm = r["remind_time"] or ""
            item = dict(
                id=r["id"], text=r["text"],
                date=_fmt(d, lg), time=tm,
                late=bool(d) and d < t
            )
            if r["done"]:
                grp["done"].append(item)
            elif not d:
                grp["nodate"].append(item)
            elif _is_due(d, tm, now):
                grp["due"].append(item)
            else:
                grp["soon"].append(item)

        return render_template(
            "ntnotes.html", L=UI[lg], grp=grp, mindate=t
        )

    def add():
        g = guard()
        if g:
            return g
        txt = (request.form.get("text") or "").strip()[:500]
        d = (request.form.get("date") or "").strip()
        tm = (request.form.get("time") or "").strip()

        try:
            if d:
                datetime.strptime(d, "%Y-%m-%d")
            if tm:
                datetime.strptime(tm, "%H:%M")
            if tm and not d:
                tm = ""
        except ValueError:
            d, tm = "", ""

        if txt:
            c = _db()
            c.execute("""
                INSERT INTO notes(text, remind_date, remind_time, created)
                VALUES(?,?,?,?)
            """, (txt, d or None, tm or None, _today().isoformat()))
            c.commit()
            c.close()
        return redirect("/notes")

    def done(i):
        g = guard()
        if g:
            return g
        c = _db()
        c.execute("UPDATE notes SET done=1-done WHERE id=?", (i,))
        c.commit()
        c.close()
        return redirect(request.form.get("next") or "/notes")

    def dele(i):
        g = guard()
        if g:
            return g
        c = _db()
        c.execute("DELETE FROM notes WHERE id=?", (i,))
        c.commit()
        c.close()
        return redirect("/notes")

    app.add_url_rule("/notes", "nt_page", page)
    app.add_url_rule("/notes/add", "nt_add", add, methods=["POST"])
    app.add_url_rule("/notes/<int:i>/done", "nt_done", done, methods=["POST"])
    app.add_url_rule("/notes/<int:i>/del", "nt_del", dele, methods=["POST"])
