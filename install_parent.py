# ClassKhata - parent read-only link.  Run inside ~/classkhata :  python install_parent.py
import os, re, shutil, sys

for p in ["app.py", "parent.py", "tenant.py", "fees.py", "templates/parent_link.html", "templates/parent_view.html", "templates/base.html"]:
    if not os.path.exists(p):
        sys.exit("NAHI MILA: %s  (sahi folder me ho? tenant wala patch laga hai?)" % p)

def bak(p):
    n = 1
    while os.path.exists("%s.par%d" % (p, n)):
        n += 1
    shutil.copy(p, "%s.par%d" % (p, n))

def rd(p): return open(p, encoding="utf-8").read()
def wr(p, s): open(p, "w", encoding="utf-8").write(s)

if "def fee_history_s" not in rd("fees.py"):
    sys.exit("NAHI MILA: fees.py me fee_history_s. Kuch change nahi hua. Mujhe 'grep -n fee_history_s fees.py' ka output bhejo.")

s = rd("app.py")
if "parent.setup" in s:
    print("SKIP app.py (pehle se juda hai)")
else:
    m = None
    for pat in (r"^absent\.setup\(.*\)[ \t]*$", r"^library\.setup\(.*\)[ \t]*$", r"^account\.setup\(.*\)[ \t]*$"):
        m = re.search(pat, s, re.M)
        if m:
            break
    if m:
        pos, add = m.end(), "\nimport parent\nparent.setup(app)"
    else:
        m = re.search(r'^if __name__\s*==\s*[\'"]__main__[\'"]\s*:', s, re.M)
        if not m:
            sys.exit("NAHI MILA: app.py me setup ya  if __name__  wali line. Kuch change nahi hua.")
        pos, add = m.start(), "import parent\nparent.setup(app)\n\n"
    bak("app.py")
    wr("app.py", s[:pos] + add + s[pos:])
    print("OK app.py")

f = "templates/student_detail.html"
if not os.path.exists(f):
    print("SKIP %s (file nahi mili)" % f)
else:
    t = rd(f)
    if "/parent" in t and "<!--PAR-->" in t:
        print("SKIP %s (button pehle se hai)" % f)
    else:
        m = re.search(r'<a class="hb" href="/students/\{\{ s\.id \}\}/card".*?</a>', t, re.S)
        if not m:
            print("NOTE: student_detail.html me card wala button nahi mila. Link seedha /students/<id>/parent par khulta hai.")
        else:
            btn = ('<!--PAR--><a class="hb" href="/students/{{ s.id }}/parent" aria-label="Parent link"><svg class="ic" viewBox="0 0 24 24">'
                   '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></svg></a><!--/PAR-->')
            bak(f)
            wr(f, t[:m.end()] + "\n" + btn + t[m.end():])
            print("OK", f)

os.system("python -m py_compile app.py parent.py && echo COMPILE-OK")
print("\nTest: bachche ka page kholo, upar link wala naya button dabao.")
