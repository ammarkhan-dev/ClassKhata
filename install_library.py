# ClassKhata - Model Paper + Books tiles.  Run inside ~/classkhata :  python install_library.py
import os, re, shutil, sys

for p in ["app.py", "library.py", "templates/home.html", "templates/modelpaper.html", "templates/books.html"]:
    if not os.path.exists(p):
        sys.exit("NAHI MILA: %s  (sahi folder me ho? cd ~/classkhata)" % p)

def bak(p):
    n = 1
    while os.path.exists("%s.lib%d" % (p, n)):
        n += 1
    shutil.copy(p, "%s.lib%d" % (p, n))

def rd(p): return open(p, encoding="utf-8").read()
def wr(p, s): open(p, "w", encoding="utf-8").write(s)

# app.py
s = rd("app.py")
if "library.setup" in s:
    print("SKIP app.py (pehle se juda hai)")
else:
    m = re.search(r"^syllabus\.setup\(.*\)[ \t]*$", s, re.M)
    if m:
        pos = m.end()
        add = "\nimport library\nlibrary.setup(app)"
    else:
        m = re.search(r'^if __name__\s*==\s*[\'"]__main__[\'"]\s*:', s, re.M)
        if not m:
            sys.exit("NAHI MILA: app.py me syllabus.setup ya  if __name__  wali line. Kuch change nahi hua.")
        pos = m.start()
        add = "import library\nlibrary.setup(app)\n\n"
    bak("app.py")
    wr("app.py", s[:pos] + add + s[pos:])
    print("OK app.py")

# home.html: two more tiles, cloned from the Syllabus tile
h = rd("templates/home.html")
if 'href="/modelpaper"' in h and 'href="/books"' in h:
    print("SKIP home.html (tiles pehle se hain)")
else:
    m = re.search(r'<a\b[^>]*href="/syllabus"[^>]*>.*?</a>', h, re.S)
    if not m:
        print("SKIP home.html: Syllabus tile nahi mila. Pehle syllabus wala pack lagao.")
    else:
        base = m.group(0)
        icons = {
            "/modelpaper": ('<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6"/><path d="M9 17h4"/></svg>',
                            "{{ 'मॉडल पेपर' if session.get('lang') == 'hi' else 'Model Paper' }}"),
            "/books": ('<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
                       "{{ 'पुस्तकें' if session.get('lang') == 'hi' else 'Books' }}"),
        }
        new = ""
        for href, (svg, label) in icons.items():
            if 'href="%s"' % href in h:
                continue
            t = base.replace('href="/syllabus"', 'href="%s"' % href)
            t = re.sub(r"<svg\b.*?</svg>", lambda _: svg, t, count=1, flags=re.S)
            ex = list(re.finditer(r"\{\{.*?\}\}", t, re.S))
            if not ex:
                print("SKIP home.html: tile ka label nahi mila"); new = None; break
            e = ex[-1]
            t = t[:e.start()] + label + t[e.end():]
            new += "\n" + t
        if new:
            bak("templates/home.html")
            wr("templates/home.html", h[:m.end()] + new + h[m.end():])
            print("OK home.html")

os.system("python -m py_compile app.py library.py && echo COMPILE-OK")
print("\nApp dobara chalao aur Home me Model Paper aur Books tiles dekho.")
