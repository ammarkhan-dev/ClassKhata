import glob, importlib, os, re
from flask import session

BASE = os.path.dirname(os.path.abspath(__file__))

def load(suffix):
    out = {}
    files = glob.glob(os.path.join(BASE, f"tr*_{suffix}.py"))
    files.sort(key=lambda f: int(re.sub(r"\D", "", os.path.basename(f)) or 0))
    for f in files:
        mod = importlib.import_module(os.path.basename(f)[:-3])
        for k in dir(mod):
            v = getattr(mod, k)
            if k.isupper() and isinstance(v, dict):
                out.update(v)
    return out

TR = {"en": load("en"), "hi": load("hi")}

def setup(app):
    @app.context_processor
    def inject():
        lang = session.get("lang", "en")
        def t(k):
            return TR.get(lang, TR["en"]).get(k) or TR["en"].get(k, k)
        return dict(t=t, lang=lang)
