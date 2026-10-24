from flask import render_template, request
import store

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
