# ClassKhata - absent students -> parent WhatsApp.  Run inside ~/classkhata :  python install_absent.py
import os, re, shutil, sys

for p in ["app.py", "absent.py", "templates/absent.html", "templates/base.html"]:
    if not os.path.exists(p):
        sys.exit("NAHI MILA: %s  (sahi folder me ho? cd ~/classkhata)" % p)

def bak(p):
    n = 1
    while os.path.exists("%s.abs%d" % (p, n)):
        n += 1
    shutil.copy(p, "%s.abs%d" % (p, n))

def rd(p): return open(p, encoding="utf-8").read()
def wr(p, s): open(p, "w", encoding="utf-8").write(s)

# ---- app.py ----
s = rd("app.py")
if "absent.setup" in s:
    print("SKIP app.py (pehle se juda hai)")
else:
    m = None
    for pat in (r"^library\.setup\(.*\)[ \t]*$", r"^account\.setup\(.*\)[ \t]*$", r"^syllabus\.setup\(.*\)[ \t]*$"):
        m = re.search(pat, s, re.M)
        if m:
            break
    if m:
        pos, add = m.end(), "\nimport absent\nabsent.setup(app)"
    else:
        m = re.search(r'^if __name__\s*==\s*[\'"]__main__[\'"]\s*:', s, re.M)
        if not m:
            sys.exit("NAHI MILA: app.py me setup ya  if __name__  wali line. Kuch change nahi hua.")
        pos, add = m.start(), "import absent\nabsent.setup(app)\n\n"
    bak("app.py")
    wr("app.py", s[:pos] + add + s[pos:])
    print("OK app.py")

# ---- button on attendance pages ----
BTN = ('<!--ABS--><a href="/hazri/absent" style="display:block;margin:4px 0 12px;padding:12px 14px;border-radius:12px;'
       'background:#1fa855;color:#fff;text-decoration:none;font-weight:600;font-size:14px;text-align:center">'
       "{{ 'अनुपस्थित अभिभावकों को संदेश' if session.get('lang') == 'hi' else 'Message parents of absent students' }}</a><!--/ABS-->")
for f in ("templates/hazri_home.html", "templates/hazri_class.html"):
    if not os.path.exists(f):
        print("SKIP %s (file nahi mili)" % f); continue
    t = rd(f)
    if "<!--ABS-->" in t:
        print("SKIP %s (button pehle se hai)" % f); continue
    m = re.search(r"\{%\s*block body\s*%\}", t)
    if not m:
        print("NOTE: %s me block body nahi mila, button nahi lagaya" % f); continue
    bak(f)
    wr(f, t[:m.end()] + "\n" + BTN + t[m.end():])
    print("OK", f)

os.system("python -m py_compile app.py absent.py && echo COMPILE-OK")
print("\nTest: app chalao, /hazri/absent kholo.")
