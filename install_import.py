# ClassKhata - import students from Excel/CSV.  Run inside ~/classkhata :  python install_import.py
import os, re, shutil, sys

for p in ["app.py", "importer.py", "students.py", "templates/import_students.html", "templates/base.html"]:
    if not os.path.exists(p):
        sys.exit("NAHI MILA: %s  (sahi folder me ho? cd ~/classkhata)" % p)

def bak(p):
    n = 1
    while os.path.exists("%s.imp%d" % (p, n)):
        n += 1
    shutil.copy(p, "%s.imp%d" % (p, n))

def rd(p): return open(p, encoding="utf-8").read()
def wr(p, s): open(p, "w", encoding="utf-8").write(s)

st = rd("students.py")
for need in ("def parse(", "def save_extra(", "def cur_session(", "def default_end(", "def digits10("):
    if need not in st:
        sys.exit("NAHI MILA: students.py me '%s'. Kuch change nahi hua." % need)

s = rd("app.py")
if "importer.setup" in s:
    print("SKIP app.py (pehle se juda hai)")
else:
    m = None
    for pat in (r"^extra\.setup\(.*\)[ \t]*$", r"^parent\.setup\(.*\)[ \t]*$", r"^absent\.setup\(.*\)[ \t]*$", r"^library\.setup\(.*\)[ \t]*$"):
        m = re.search(pat, s, re.M)
        if m:
            break
    if m:
        pos, add = m.end(), "\nimport importer\nimporter.setup(app)"
    else:
        m = re.search(r'^if __name__\s*==\s*[\'"]__main__[\'"]\s*:', s, re.M)
        if not m:
            sys.exit("NAHI MILA: app.py me setup ya  if __name__  wali line. Kuch change nahi hua.")
        pos, add = m.start(), "import importer\nimporter.setup(app)\n\n"
    bak("app.py")
    wr("app.py", s[:pos] + add + s[pos:])
    print("OK app.py")

# link on the students list page
f = "templates/students.html"
BTN = ('<!--IMP--><a href="/students/import" style="display:block;margin:6px 0 12px;padding:11px 14px;border-radius:12px;background:#fff;'
       'color:#222f40;text-decoration:none;font-weight:600;font-size:14px;text-align:center;box-shadow:0 1px 3px rgba(15,23,42,.1)">'
       "{{ 'Excel / CSV से विद्यार्थी इम्पोर्ट' if session.get('lang') == 'hi' else 'Import students from Excel / CSV' }}</a><!--/IMP-->")
if not os.path.exists(f):
    print("SKIP %s (file nahi mili). Page seedha /students/import par khulta hai." % f)
else:
    t = rd(f)
    if "<!--IMP-->" in t:
        print("SKIP %s (button pehle se hai)" % f)
    else:
        m = re.search(r"\{%\s*block body\s*%\}", t)
        if not m:
            print("NOTE: %s me block body nahi mila. Page seedha /students/import par kholo." % f)
        else:
            bak(f)
            wr(f, t[:m.end()] + "\n" + BTN + t[m.end():])
            print("OK", f)

os.system("python -m py_compile app.py importer.py && echo COMPILE-OK")
print("\nTest: Students page par 'Import' button dabao.")
