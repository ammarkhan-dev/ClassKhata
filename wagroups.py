"""ClassKhata - WhatsApp groups per batch + one message for many groups."""
import sqlite3
from flask import render_template, request, redirect
import absent

UI = {
    "en": dict(title="WhatsApp groups", sub="Groups of this batch", name="Group name", link="Invite link (optional)",
               add="Add group", none="No groups yet", back="Batch", delete="Delete", sure="Delete this group?",
               badlink="Link must start with https://chat.whatsapp.com/",
               btitle="Message groups", bsub="Write once, send to many", msg="Message",
               prep="Prepare", pick="Select groups", nogroups="Add groups inside a batch first.",
               copyopen="Copy + open group", pickgroup="Open WhatsApp, pick group",
               hint="Message is copied. Paste it in the group and press send.", done="Done", empty="Write a message and select groups."),
    "hi": dict(title="WhatsApp ग्रुप", sub="इस बैच के ग्रुप", name="ग्रुप का नाम", link="इन्वाइट लिंक (वैकल्पिक)",
               add="ग्रुप जोड़ें", none="अभी कोई ग्रुप नहीं", back="बैच", delete="हटाएँ", sure="यह ग्रुप हटाएँ?",
               badlink="लिंक https://chat.whatsapp.com/ से शुरू होना चाहिए",
               btitle="ग्रुप में संदेश", bsub="एक बार लिखें, कई ग्रुप में भेजें", msg="संदेश",
               prep="तैयार करें", pick="ग्रुप चुनें", nogroups="पहले किसी बैच में ग्रुप जोड़ें।",
               copyopen="कॉपी + ग्रुप खोलें", pickgroup="WhatsApp खोलें, ग्रुप चुनें",
               hint="संदेश कॉपी हो गया। ग्रुप में पेस्ट करके भेजें।", done="हो गया", empty="संदेश लिखें और ग्रुप चुनें।"),
}


def _con():
    c = sqlite3.connect("classkhata.db")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS batch_groups(id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "batch_id INTEGER, name TEXT NOT NULL, link TEXT)")
    return c


def setup(app, db=None):
    @app.context_processor
    def _wa_ctx():
        def wa_count():
            try:
                c = _con()
                n = c.execute('SELECT COUNT(*) FROM batch_groups').fetchone()[0]
                c.close()
                return n
            except Exception:
                return 0
        return dict(wa_count=wa_count)

    @app.route("/batches/<int:bid>/groups", methods=["GET", "POST"])
    def batch_groups(bid):
        L = UI[absent._lang()]
        c = _con()
        b = c.execute("SELECT id, name FROM batches WHERE id=?", (bid,)).fetchone()
        if not b:
            c.close()
            return redirect("/batches")
        err = None
        if request.method == "POST":
            name = request.form.get("name", "").strip()[:60]
            link = request.form.get("link", "").strip()
            if link and not link.startswith("https://chat.whatsapp.com/"):
                err = L["badlink"]
            elif name:
                c.execute("INSERT INTO batch_groups(batch_id,name,link) VALUES(?,?,?)", (bid, name, link))
                c.commit()
        rows = c.execute("SELECT * FROM batch_groups WHERE batch_id=? ORDER BY name COLLATE NOCASE", (bid,)).fetchall()
        c.close()
        return render_template("batch_groups.html", L=L, b=b, rows=rows, err=err)

    @app.route("/batches/groups/<int:gid>/delete", methods=["POST"])
    def batch_group_delete(gid):
        c = _con()
        r = c.execute("SELECT batch_id FROM batch_groups WHERE id=?", (gid,)).fetchone()
        c.execute("DELETE FROM batch_groups WHERE id=?", (gid,))
        c.commit()
        c.close()
        return redirect("/batches/%d/groups" % r["batch_id"] if r else "/batches")

    @app.route("/broadcast")
    def broadcast():
        L = UI[absent._lang()]
        c = _con()
        rows = c.execute("SELECT g.id, g.name, g.link, b.name bname FROM batch_groups g "
                         "JOIN batches b ON b.id=g.batch_id "
                         "ORDER BY b.name COLLATE NOCASE, g.name COLLATE NOCASE").fetchall()
        c.close()
        return render_template("broadcast.html", L=L, groups=[dict(r) for r in rows])
