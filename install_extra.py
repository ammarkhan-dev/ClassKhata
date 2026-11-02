# ClassKhata - previous due + extra fee.  Run inside ~/classkhata :  python install_extra.py
import os, re, shutil, sys

for p in ["app.py", "extra.py", "fees.py", "feesview.py", "studentview.py", "templates/extra_dues.html", "templates/student_detail.html"]:
    if not os.path.exists(p):
        sys.exit("NAHI MILA: %s  (sahi folder me ho? cd ~/classkhata)" % p)

def bak(p):
    n = 1
    while os.path.exists("%s.ext%d" % (p, n)):
        n += 1
    shutil.copy(p, "%s.ext%d" % (p, n))

def rd(p): return open(p, encoding="utf-8").read()
def wr(p, s): open(p, "w", encoding="utf-8").write(s)

def patch(path, steps, marker):
    s = rd(path)
    if marker in s:
        print("SKIP %s (pehle se patched)" % path); return
    for old, new in steps:
        if s.count(old) != 1:
            sys.exit("NAHI MILA (%s): %s\nKuch change nahi hua (is file me). Ye line mujhe bhej do." % (path, old.strip()[:90]))
        s = s.replace(old, new)
    bak(path); wr(path, s); print("OK", path)

# ---- check everything first, so nothing is half-patched ----
need = {
 "fees.py": ['def fee_history_s(db, sid, adm, fee, pm, today):\n    a0, _x = sched(db, sid, adm)\n    return fee_history(a0, fee, pm, today)\n'],
 "feesview.py": ["        if not s or not mkey_ok(month):\n", "        if sid is None or not mkey_ok(month):\n", "        y, m = int(month[:4]), int(month[5:])\n"],
 "studentview.py": ["    def student_pay(sid, month):\n        s = get(sid)\n", "label=f\"{MONTHS[lang][h['m'] - 1]} {h['y']}\",", '        remind = wa_link(s, due[0]["baaki"], due[0]["due"], due[0]["y"], due[0]["m"], lang) if due else ""\n'],
}
MARK = {"fees.py": "import extra", "feesview.py": '__import__("extra")', "studentview.py": "import extra"}
for f, olds in need.items():
    t = rd(f)
    if MARK[f] in t:
        continue
    for o in olds:
        if t.count(o) != 1:
            sys.exit("NAHI MILA (%s): %s\nKuch change nahi hua. Ye line mujhe bhej do." % (f, o.strip()[:90]))

patch("fees.py", [(need["fees.py"][0],
 'def fee_history_s(db, sid, adm, fee, pm, today):\n    a0, _x = sched(db, sid, adm)\n    hist = fee_history(a0, fee, pm, today)\n'
 '    try:\n        import extra\n        return extra.entries(db, sid, pm, today) + list(hist)\n    except Exception:\n        return hist\n')], "import extra")

patch("feesview.py", [
 ("        if not s or not mkey_ok(month):\n", '        if not s or not (mkey_ok(month) or __import__("extra").ok(month)):\n'),
 ("        if sid is None or not mkey_ok(month):\n", '        if sid is None or not (mkey_ok(month) or __import__("extra").ok(month)):\n'),
 ("        y, m = int(month[:4]), int(month[5:])\n",
  '        if month.startswith("X"):\n            __import__("extra").pay(db, sid, month, mode)\n            return redirect(safe_next(request.form.get("next", "")))\n        y, m = int(month[:4]), int(month[5:])\n'),
], '__import__("extra")')

patch("studentview.py", [
 ("    def student_pay(sid, month):\n        s = get(sid)\n",
  '    def student_pay(sid, month):\n        s = get(sid)\n        if month.startswith("X"):\n            import extra\n            extra.pay(db, sid, month, "")\n            return redirect(f"/students/{sid}")\n'),
 ("label=f\"{MONTHS[lang][h['m'] - 1]} {h['y']}\",", "label=(h.get(\"label\") or f\"{MONTHS[lang][h['m'] - 1]} {h['y']}\"),"),
 ('        remind = wa_link(s, due[0]["baaki"], due[0]["due"], due[0]["y"], due[0]["m"], lang) if due else ""\n',
  '        _reg = [h for h in due if not h.get("extra")]\n        _xb = sum(h["baaki"] for h in due if h.get("extra"))\n'
  '        _f = (_reg or due)[0]\n'
  '        remind = wa_link(s, (_f["baaki"] if _reg else 0) + _xb, _f["due"], _f["y"], _f["m"], lang) if due else ""\n'),
], "import extra")

# parent.py (optional): show the entry's own name instead of a month name
if os.path.exists("parent.py"):
    t = rd("parent.py")
    o = 'label="%s %d" % (MONTHS[lg][x["m"] - 1], x["y"])'
    if 'x.get("label")' in t:
        print("SKIP parent.py")
    elif t.count(o) == 1:
        bak("parent.py"); wr("parent.py", t.replace(o, 'label=(x.get("label") or "%s %d" % (MONTHS[lg][x["m"] - 1], x["y"]))')); print("OK parent.py")
    else:
        print("NOTE: parent.py me label wali line nahi mili (parent link me extra ka naam mahine ki tarah dikh sakta hai)")

# app.py
s = rd("app.py")
if "extra.setup" in s:
    print("SKIP app.py")
else:
    m = None
    for pat in (r"^parent\.setup\(.*\)[ \t]*$", r"^absent\.setup\(.*\)[ \t]*$", r"^library\.setup\(.*\)[ \t]*$"):
        m = re.search(pat, s, re.M)
        if m: break
    if m:
        pos, add = m.end(), "\nimport extra\nextra.setup(app)"
    else:
        m = re.search(r'^if __name__\s*==\s*[\'"]__main__[\'"]\s*:', s, re.M)
        if not m: sys.exit("NAHI MILA: app.py me setup ya  if __name__  wali line.")
        pos, add = m.start(), "import extra\nextra.setup(app)\n\n"
    bak("app.py"); wr("app.py", s[:pos] + add + s[pos:]); print("OK app.py")

# button on student page (next to the card button)
f = "templates/student_detail.html"
t = rd(f)
if "<!--EXT-->" in t:
    print("SKIP student_detail.html")
else:
    m = re.search(r'<a class="hb" href="/students/\{\{ s\.id \}\}/card".*?</a>', t, re.S)
    if not m:
        print("NOTE: card wala button nahi mila. Page seedha /students/<id>/extra par khulta hai.")
    else:
        btn = ('<!--EXT--><a class="hb" href="/students/{{ s.id }}/extra" aria-label="Extra fee"><svg class="ic" viewBox="0 0 24 24">'
               '<path d="M12 5v14M5 12h14"/></svg></a><!--/EXT-->')
        bak(f); wr(f, t[:m.end()] + "\n" + btn + t[m.end():]); print("OK", f)

os.system("python -m py_compile app.py extra.py fees.py feesview.py studentview.py && echo COMPILE-OK")
print("\nTest: bachche ke page par naya + button dabao, 'Purana baaki' daalo.")
