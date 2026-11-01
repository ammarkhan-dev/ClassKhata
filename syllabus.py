"""ClassKhata - Syllabus (UP Board, Hindi medium) : class -> subject -> chapter -> topic -> subtopic.
Data lives in syl_data/*.txt  (edit these files to change the syllabus).
Line format:  @class 12 | @subject key | English | Hindi | # chapter | ## topic | - subtopic
Every name is written as  English | Hindi  and shown in the app language.
"""
import os
from flask import render_template, session, abort

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "syl_data")

UI = {
    "en": {"title": "Syllabus", "sub": "UP Board (UPMSP)", "pick_class": "Choose class",
           "class": "Class", "subjects": "subjects", "chapters": "chapters",
           "topics": "topics", "subtopics": "subtopics", "chapter": "Chapter",
           "open": "Tap a topic to see its subtopics", "empty": "Nothing here yet",
           "board": "UP Board - Hindi medium", "note": "Based on UPMSP pattern. Confirm with your school book list."},
    "hi": {"title": "पाठ्यक्रम", "sub": "यूपी बोर्ड (UPMSP)", "pick_class": "कक्षा चुनें",
           "class": "कक्षा", "subjects": "विषय", "chapters": "अध्याय",
           "topics": "टॉपिक", "subtopics": "उप-टॉपिक", "chapter": "अध्याय",
           "open": "उप-टॉपिक देखने के लिए टॉपिक दबाएँ", "empty": "अभी कुछ नहीं है",
           "board": "यूपी बोर्ड - हिन्दी माध्यम", "note": "UPMSP पैटर्न पर आधारित। अपनी स्कूल पुस्तक सूची से मिला लें।"},
}

_cache = {}


def _pair(s):
    if "|" in s:
        a, b = s.split("|", 1)
        return {"en": a.strip(), "hi": b.strip()}
    s = s.strip()
    return {"en": s, "hi": s}


def load():
    """Return {class: [subject,...]} ; subject = {key,en,hi,chapters:[{en,hi,topics:[{en,hi,subs:[{en,hi}]}]}]}"""
    if _cache:
        return _cache
    out = {}
    if not os.path.isdir(DATA):
        return out
    for fn in sorted(os.listdir(DATA)):
        if not fn.endswith(".txt"):
            continue
        cls = sub = ch = tp = None
        for raw in open(os.path.join(DATA, fn), encoding="utf-8"):
            ln = raw.rstrip("\n")
            if not ln.strip():
                continue
            if ln.startswith("@class"):
                cls = ln.split(None, 1)[1].strip()
            elif ln.startswith("@subject"):
                parts = [p.strip() for p in ln[len("@subject"):].split("|")]
                sub = {"key": parts[0], "en": parts[1], "hi": parts[2], "chapters": []}
                out.setdefault(cls, []).append(sub)
            elif ln.startswith("## "):
                tp = dict(_pair(ln[3:]), subs=[])
                ch["topics"].append(tp)
            elif ln.startswith("# "):
                ch = dict(_pair(ln[2:]), topics=[])
                sub["chapters"].append(ch)
            elif ln.startswith("- "):
                tp["subs"].append(_pair(ln[2:]))
    _cache.update(out)
    return _cache


ORDER = ["physics", "chemistry", "maths", "biology", "english", "hindi",
         "science", "social"]


def _lang():
    return "hi" if session.get("lang") == "hi" else "en"


def _counts(sub):
    ch = sub["chapters"]
    tp = sum(len(c["topics"]) for c in ch)
    st = sum(len(t["subs"]) for c in ch for t in c["topics"])
    return len(ch), tp, st


def _subject(cls, key):
    for s in load().get(cls, []):
        if s["key"] == key:
            return s
    abort(404)


def setup(app, db=None):
    @app.route("/syllabus")
    def syl_home():
        d = load()
        rows = []
        for c in sorted(d, key=int):
            n = len(d[c])
            rows.append({"cls": c, "n": n})
        return render_template("syllabus_home.html", L=UI[_lang()], lang=_lang(), rows=rows)

    @app.route("/syllabus/<cls>")
    def syl_class(cls):
        d = load()
        if cls not in d:
            abort(404)
        subs = []
        for s in sorted(d[cls], key=lambda s: ORDER.index(s["key"]) if s["key"] in ORDER else 99):
            c, t, st = _counts(s)
            subs.append({"key": s["key"], "name": s[_lang()], "ch": c, "tp": t, "st": st})
        return render_template("syllabus_class.html", L=UI[_lang()], lang=_lang(), cls=cls, subs=subs)

    @app.route("/syllabus/<cls>/<key>")
    def syl_subject(cls, key):
        s = _subject(cls, key)
        lg = _lang()
        chs = [{"i": i + 1, "name": c[lg], "tp": len(c["topics"]),
                "st": sum(len(t["subs"]) for t in c["topics"])}
               for i, c in enumerate(s["chapters"])]
        return render_template("syllabus_subject.html", L=UI[lg], lang=lg, cls=cls,
                               key=key, sname=s[lg], chs=chs)

    @app.route("/syllabus/<cls>/<key>/<int:n>")
    def syl_chapter(cls, key, n):
        s = _subject(cls, key)
        lg = _lang()
        if n < 1 or n > len(s["chapters"]):
            abort(404)
        c = s["chapters"][n - 1]
        tps = [{"name": t[lg], "subs": [x[lg] for x in t["subs"]]} for t in c["topics"]]
        return render_template("syllabus_chapter.html", L=UI[lg], lang=lg, cls=cls, key=key,
                               sname=s[lg], n=n, total=len(s["chapters"]), cname=c[lg], tps=tps)
