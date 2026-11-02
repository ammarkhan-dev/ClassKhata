"""ClassKhata - 'Backup' page: download your own data file + see the server's last daily copy."""
import os
import sqlite3
import tempfile
from datetime import date, datetime
from flask import abort, after_this_request, render_template, send_file, session

import tenant

UI = {
    "en": dict(title="Backup", sub="Keep your data safe", dl="Download my data", last="Server's last automatic copy",
               never="Not yet", why="Your data is stored on the server. Download a copy to your phone now and then (for example every week) and keep it somewhere safe, such as Google Drive.",
               size="Size", note="This file has only your coaching's data (students, fees, attendance, expenses). It does not contain passwords.",
               how="To restore, send this file to your developer.", back="Back", daily="The server also keeps a copy every day for 14 days."),
    "hi": dict(title="बैकअप", sub="अपना डेटा सुरक्षित रखें", dl="मेरा डेटा डाउनलोड करें", last="सर्वर की आख़िरी अपने-आप बनी कॉपी",
               never="अभी नहीं", why="आपका डेटा सर्वर पर रखा है। समय-समय पर (जैसे हर हफ़्ते) अपने फ़ोन में एक कॉपी डाउनलोड करके सुरक्षित जगह रखें, जैसे Google Drive।",
               size="साइज़", note="इस फ़ाइल में सिर्फ़ आपकी कोचिंग का डेटा है (विद्यार्थी, फ़ीस, उपस्थिति, ख़र्चे)। पासवर्ड इसमें नहीं हैं।",
               how="वापस डालने के लिए यह फ़ाइल अपने डेवलपर को भेजें।", back="वापस", daily="सर्वर हर दिन भी एक कॉपी रखता है, 14 दिन तक।"),
}


def _mine():
    try:
        tid = int(session.get("tid") or session.get("uid") or 0)
    except (TypeError, ValueError):
        tid = 0
    p = tenant.path_for(tid) if tid else ""
    return p if p and os.path.exists(p) else ""


def _last_server_copy():
    d = os.path.join(os.path.dirname(os.path.abspath(tenant.__file__)), "backups")
    try:
        days = sorted(x for x in os.listdir(d) if len(x) == 10 and x[4] == "-")
        return days[-1] if days else ""
    except OSError:
        return ""


def setup(app, db=None):
    @app.route("/mybackup")
    def mybackup_page():
        lg = "hi" if session.get("lang") == "hi" else "en"
        p = _mine()
        kb = round(os.path.getsize(p) / 1024) if p else 0
        return render_template("mybackup.html", L=UI[lg], size=("%d KB" % kb) if p else "", has=bool(p), last=_last_server_copy())

    @app.route("/mybackup/download")
    def mybackup_download():
        p = _mine()
        if not p:
            abort(404)
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        src = tenant.raw_connect(p)
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        @after_this_request
        def _rm(resp):
            try:
                os.remove(tmp)
            except OSError:
                pass
            return resp

        resp = send_file(tmp, mimetype="application/octet-stream", as_attachment=True,
                         download_name="classkhata-backup-%s.db" % date.today().isoformat())
        resp.headers["Cache-Control"] = "no-store"
        return resp
