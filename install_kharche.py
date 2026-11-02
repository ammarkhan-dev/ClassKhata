# ClassKhata - expenses + monthly profit.  Run inside ~/classkhata :  python install_kharche.py
import os, re, shutil, sys

for p in ["app.py", "kharche.py", "templates/kharche.html", "templates/home.html", "templates/base.html"]:
    if not os.path.exists(p):
        sys.exit("NAHI MILA: %s  (sahi folder me ho? cd ~/classkhata)" % p)

def bak(p):
    n = 1
    while os.path.exists("%s.khr%d" % (p, n)):
        n += 1
    shutil.copy(p, "%s.khr%d" % (p, n))

def rd(p): return open(p, encoding="utf-8").read()
def wr(p, s): open(p, "w", encoding="utf-8").write(s)

s = rd("app.py")
if "kharche.setup" in s:
    print("SKIP app.py (pehle se juda hai)")
else:
    m = None
    for pat in (r"^importer\.setup\(.*\)[ \t]*$", r"^extra\.setup\(.*\)[ \t]*$", r"^parent\.setup\(.*\)[ \t]*$", r"^absent\.setup\(.*\)[ \t]*$", r"^library\.setup\(.*\)[ \t]*$"):
        m = re.search(pat, s, re.M)
        if m:
            break
    if m:
        pos, add = m.end(), "\nimport kharche\nkharche.setup(app)"
    else:
        m = re.search(r'^if __name__\s*==\s*[\'"]__main__[\'"]\s*:', s, re.M)
        if not m:
            sys.exit("NAHI MILA: app.py me setup ya  if __name__  wali line. Kuch change nahi hua.")
        pos, add = m.start(), "import kharche\nkharche.setup(app)\n\n"
    bak("app.py")
    wr("app.py", s[:pos] + add + s[pos:])
    print("OK app.py")

h = rd("templates/home.html")
if 'href="/kharche"' in h:
    print("SKIP home.html (tile pehle se hai)")
else:
    m = re.search(r'<a\b[^>]*href="/syllabus"[^>]*>.*?</a>', h, re.S) or re.search(r'<a\b[^>]*href="/books"[^>]*>.*?</a>', h, re.S)
    if not m:
        print("SKIP home.html: Syllabus/Books tile nahi mila. Page seedha /kharche par khulta hai.")
    else:
        svg = ('<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
               '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18"/><path d="M7 15h4"/></svg>')
        label = "{{ 'ख़र्चे' if session.get('lang') == 'hi' else 'Expenses' }}"
        t = m.group(0).replace(re.search(r'href="[^"]*"', m.group(0)).group(0), 'href="/kharche"', 1)
        t = re.sub(r"<svg\b.*?</svg>", lambda _: svg, t, count=1, flags=re.S)
        ex = list(re.finditer(r"\{\{.*?\}\}", t, re.S))
        if not ex:
            print("SKIP home.html: tile ka label nahi mila. Page seedha /kharche par khulta hai.")
        else:
            e = ex[-1]
            t = t[:e.start()] + label + t[e.end():]
            # put it after the last of our tiles (books if present, else syllabus)
            last = None
            for mm in re.finditer(r'<a\b[^>]*href="/(?:syllabus|modelpaper|books)"[^>]*>.*?</a>', h, re.S):
                last = mm
            bak("templates/home.html")
            wr("templates/home.html", h[:last.end()] + "\n" + t + h[last.end():])
            print("OK home.html")

os.system("python -m py_compile app.py kharche.py && echo COMPILE-OK")
print("\nTest: Home par 'Expenses' tile dabao.")
