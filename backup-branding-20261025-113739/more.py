import csv, io, json, os, sqlite3, tempfile
from datetime import date
from flask import render_template, request, Response, send_file, send_from_directory, abort
import store

BASE = os.path.dirname(os.path.abspath(__file__))

def safe(v):
    if v is None:
        return ""
    v = str(v)
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v

def csv_response(name, header, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow([safe(x) for x in r])
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})

def backup_info():
    last = store.get("last_backup", "")
    try:
        days = (date.today() - date.fromisoformat(last)).days
    except ValueError:
        return "", True
    return last, days > 7

ALL = ("WITH allst AS (SELECT id,name,cls,acad_session FROM students "
       "UNION ALL SELECT id,name,cls,acad_session FROM records) ")
HEAD = ["Name", "Class", "Parent name", "Parent phone", "Monthly fee", "Admission date", "Session", "Session ends"]
EXPORTS = {
    "students": ("students", HEAD,
        "SELECT name,cls,parent_name,parent_phone,monthly_fee,admission_date,acad_session,session_end "
        "FROM students ORDER BY cls, name COLLATE NOCASE"),
    "records": ("records", HEAD + ["Moved to records on"],
        "SELECT name,cls,parent_name,parent_phone,monthly_fee,admission_date,acad_session,session_end,archived_on "
        "FROM records ORDER BY acad_session DESC, cls, name COLLATE NOCASE"),
    "fees": ("fee-payments", ["Student", "Class", "Session", "Fee month", "Amount", "Paid on"],
        ALL + "SELECT a.name,a.cls,a.acad_session,p.month,p.amount,p.paid_on FROM payments p "
        "LEFT JOIN allst a ON a.id=p.student_id ORDER BY p.paid_on, a.cls, a.name"),
    "attendance": ("attendance", ["Date", "Class", "Student", "Session", "Status"],
        ALL + "SELECT t.day,a.cls,a.name,a.acad_session,CASE t.status WHEN 'P' THEN 'Present' ELSE 'Absent' END "
        "FROM attendance t LEFT JOIN allst a ON a.id=t.student_id ORDER BY t.day, a.cls, a.name"),
}

def setup(app, db):
    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        saved = False
        if request.method == "POST":
            name = request.form.get("inst", "").strip()[:80]
            if name:
                store.put("institute", name)
                saved = True
        return render_template("settings.html", saved=saved)

    @app.route("/more")
    def more():
        last, due = backup_info()
        return render_template("more.html", due=due)

    @app.route("/backup")
    def backup():
        last, due = backup_info()
        return render_template("backup.html", last=last, due=due)

    @app.route("/backup/download")
    def backup_download():
        src = sqlite3.connect("classkhata.db")
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        with open(tmp, "rb") as f:
            data = f.read()
        os.remove(tmp)
        store.put("last_backup", date.today().isoformat())
        return send_file(io.BytesIO(data), as_attachment=True, mimetype="application/octet-stream",
                         download_name=f"classkhata-backup-{date.today().isoformat()}.db")

    @app.route("/export/<kind>.csv")
    def export(kind):
        if kind not in EXPORTS:
            abort(404)
        name, header, sql = EXPORTS[kind]
        rows = db().execute(sql).fetchall()
        return csv_response(f"classkhata-{name}-{date.today().isoformat()}.csv", header, rows)

    @app.route("/manifest.webmanifest")
    def manifest():
        m = {"name": store.get("institute") or "ClassKhata", "short_name": "ClassKhata",
             "description": "Coaching management: students, attendance and fees",
             "start_url": "/", "scope": "/", "display": "standalone",
             "background_color": "#222f40", "theme_color": "#222f40",
             "icons": [
                 {"src": "/static/icon-192.png?v=3", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                 {"src": "/static/icon-512.png?v=3", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                 {"src": "/static/icon-512.png?v=3", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}
        return Response(json.dumps(m), mimetype="application/manifest+json")

    @app.route("/sw.js")
    def sw():
        r = send_from_directory(BASE, "sw.js", mimetype="application/javascript")
        r.headers["Cache-Control"] = "no-cache"
        return r
