from flask import session
from tr_en import EN
from tr_hi import HI
from tr2_en import EN2
from tr2_hi import HI2
from tr3_en import EN3
from tr3_hi import HI3
from tr4_en import EN4
from tr4_hi import HI4

TR = {"en": {**EN, **EN2, **EN3, **EN4}, "hi": {**HI, **HI2, **HI3, **HI4}}

def setup(app):
    @app.context_processor
    def inject():
        lang = session.get("lang", "en")
        def t(k):
            return TR.get(lang, TR["en"]).get(k) or TR["en"].get(k, k)
        return dict(t=t, lang=lang)
