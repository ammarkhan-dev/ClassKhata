# BatchBook - Syllabus installer. Run inside ~/classkhata :  python install_syllabus.py
import os, re, shutil, sys

need = ["app.py", "syllabus.py", "syl_data", "templates/home.html", "templates/syllabus_home.html"]
for p in need:
    if not os.path.exists(p):
        sys.exit("NAHI MILA: %s  (sahi folder me ho? cd ~/classkhata)" % p)

def backup(p):
    n = 1
    while os.path.exists("%s.syl%d" % (p, n)):
        n += 1
    shutil.copy(p, "%s.syl%d" % (p, n))

# 1) app.py : register routes
s = open("app.py", encoding="utf-8").read()
if "syllabus.setup" in s:
    print("SKIP app.py (pehle se juda hai)")
else:
    m = re.search(r'^if __name__\s*==\s*[\'"]__main__[\'"]\s*:', s, re.M)
    if not m:
        sys.exit("NAHI MILA: app.py me  if __name__ == '__main__'  wali line")
    backup("app.py")
    add = "import syllabus\nsyllabus.setup(app, db)\n\n"
    s = s[:m.start()] + add + s[m.start():]
    open("app.py", "w", encoding="utf-8").write(s)
    print("OK app.py")

# 2) home.html : 4th quick-action tile
h = open("templates/home.html", encoding="utf-8").read()
if 'href="/syllabus"' in h:
    print("SKIP home.html (tile pehle se hai)")
else:
    m = re.search(r'<a\b[^>]*href="/fees"[^>]*>.*?</a>', h, re.S)
    if not m:
        print("SKIP home.html: /fees wala tile nahi mila. Tile haath se jodna ho to /syllabus link kisi bhi jagah rakh do.")
    else:
        tile = m.group(0)
        tile = tile.replace('href="/fees"', 'href="/syllabus"')
        book = ('<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#fff" stroke-width="2" '
                'stroke-linecap="round" stroke-linejoin="round"><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/>'
                '<path d="M4 21V5"/><path d="M9 8h6"/><path d="M9 12h6"/></svg>')
        if re.search(r'<svg\b.*?</svg>', tile, re.S):
            tile = re.sub(r'<svg\b.*?</svg>', book, tile, count=1, flags=re.S)
        label = "{{ 'पाठ्यक्रम' if session.get('lang') == 'hi' else 'Syllabus' }}"
        exprs = list(re.finditer(r'\{\{.*?\}\}', tile, re.S))
        if exprs:
            e = exprs[-1]
            tile = tile[:e.start()] + label + tile[e.end():]
        else:
            tile = re.sub(r'(</div>\s*)([^<>{}]+?)(\s*</a>)', lambda x: x.group(1) + label + x.group(3), tile, count=1, flags=re.S)
        backup("templates/home.html")
        h = h[:m.end()] + "\n" + tile + h[m.end():]
        # 3 tiles in a row -> 2 x 2 grid so four tiles fit nicely
        h2 = re.sub(r'(\.qa\s*\{[^}]*?grid-template-columns\s*:\s*)repeat\(3\s*,\s*1fr\)', r'\1repeat(2,1fr)', h)
        if h2 == h:
            print("NOTE: .qa grid ka CSS nahi badla (shayad pehle se alag hai) - tile phir bhi juda hai")
        h = h2
        open("templates/home.html", "w", encoding="utf-8").write(h)
        print("OK home.html")

os.system("python -m py_compile app.py syllabus.py && echo COMPILE-OK")
print("\nAb Termux me app dobara chalao (Ctrl+C phir python app.py) aur Home -> Syllabus kholo.")
