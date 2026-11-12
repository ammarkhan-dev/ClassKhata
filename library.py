"""BatchBook - Model Paper and Books sections (pages are ready; content comes next)."""
from flask import render_template, session

UI = {
    "en": {"mp": "Model Paper", "bk": "Books", "empty": "Nothing added yet", "soon": "This section is ready. Content will appear here soon.", "back": "Home"},
    "hi": {"mp": "मॉडल पेपर", "bk": "पुस्तकें", "empty": "अभी कुछ जोड़ा नहीं गया है", "soon": "यह सेक्शन तैयार है। सामग्री जल्द यहाँ दिखेगी।", "back": "होम"},
}


def _lg():
    return "hi" if session.get("lang") == "hi" else "en"


def setup(app, db=None):
    @app.route("/modelpaper")
    def model_paper():
        lg = _lg()
        return render_template("modelpaper.html", L=UI[lg], lang=lg)

    @app.route("/books")
    def books():
        lg = _lg()
        return render_template("books.html", L=UI[lg], lang=lg)
