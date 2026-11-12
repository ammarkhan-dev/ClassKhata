# BatchBook - 'Aaj ki classes' on Home.  Run inside ~/classkhata :  python install_todayc.py
import os, re, shutil, sys

for p in ["app.py", "todayc.py", "templates/home.html"]:
    if not os.path.exists(p):
        sys.exit("NAHI MILA: %s  (sahi folder me ho? cd ~/classkhata)" % p)

def bak(p):
    n = 1
    while os.path.exists("%s.tdc%d" % (p, n)):
        n += 1
    shutil.copy(p, "%s.tdc%d" % (p, n))

def rd(p): return open(p, encoding="utf-8").read()
def wr(p, s): open(p, "w", encoding="utf-8").write(s)

s = rd("app.py")
if "todayc.setup" in s:
    print("SKIP app.py (pehle se juda hai)")
else:
    m = None
    for pat in (r"^kharche\.setup\(.*\)[ \t]*$", r"^backup\.setup\(.*\)[ \t]*$", r"^importer\.setup\(.*\)[ \t]*$", r"^extra\.setup\(.*\)[ \t]*$", r"^parent\.setup\(.*\)[ \t]*$"):
        m = re.search(pat, s, re.M)
        if m:
            break
    if m:
        pos, add = m.end(), "\nimport todayc\ntodayc.setup(app)"
    else:
        m = re.search(r'^if __name__\s*==\s*[\'"]__main__[\'"]\s*:', s, re.M)
        if not m:
            sys.exit("NAHI MILA: app.py me setup ya  if __name__  wali line. Kuch change nahi hua.")
        pos, add = m.start(), "import todayc\ntodayc.setup(app)\n\n"
    bak("app.py")
    wr("app.py", s[:pos] + add + s[pos:])
    print("OK app.py")

CARD = '''<!--TC-->{% set _tc = today_classes() %}{% if _tc.has %}
<div style="background:var(--card,#fff);border:1px solid var(--line,#e6ebf1);border-radius:20px;padding:16px 18px;margin-bottom:14px">
<div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px"><b style="font-size:19px;color:var(--navy,#222f40)">{{ _tc.title }}</b><span style="font-size:13px;color:var(--muted,#64748b)">{{ _tc.date }}</span></div>
{% for c in _tc["items"] %}<a href="/hazri" style="display:flex;align-items:center;gap:10px;padding:11px 0;text-decoration:none;color:inherit;{% if not loop.first %}border-top:1px solid var(--line,#eef2f7);{% endif %}{% if c.st == 'done' %}opacity:.55{% endif %}">
<div style="flex:1;min-width:0"><b style="display:block;font-size:15px">{{ c.name }}</b><span style="font-size:13px;color:var(--muted,#64748b)">{{ c.when }} · {{ c.n }} {{ _tc.L.stu }}</span></div>
<span style="font-size:12px;font-weight:700;padding:4px 10px;border-radius:99px;{% if c.st == 'now' %}background:#e7f6ec;color:#1a7f3c{% elif c.st == 'next' %}background:#eef2f6;color:#334155{% else %}background:#f1f5f9;color:#64748b{% endif %}">{{ c.label }}</span></a>
{% else %}<div style="padding:10px 0 2px;font-size:14px;color:var(--muted,#64748b)">{{ _tc.L.none }}</div>{% endfor %}
</div>{% endif %}<!--/TC-->
'''
f = "templates/home.html"
h = rd(f)
if "<!--TC-->" in h:
    print("SKIP home.html (card pehle se hai)")
else:
    q = re.search(r'class="qt"', h)
    ok = False
    if q:
        before = h[:q.start()]
        tags = list(re.finditer(r"<(?:div|section)\b[^>]*>", before))
        if tags:
            t = tags[-1]
            between = before[t.end():]
            if len(between) < 250 and "</div>" not in between and "</section>" not in between:
                bak(f)
                wr(f, h[:t.start()] + CARD + h[t.start():])
                print("OK home.html (Quick actions ke upar)")
                ok = True
    if not ok:
        m = re.search(r"\{%\s*block body\s*%\}", h)
        if not m:
            print("NOTE: home.html me jagah nahi mili. Mujhe 'sed -n 1,12p templates/home.html' ka output bhejo.")
        else:
            bak(f)
            wr(f, h[:m.end()] + "\n" + CARD + h[m.end():])
            print("OK home.html (sabse upar, Quick actions wali jagah nahi mili)")

os.system("python -m py_compile app.py todayc.py && echo COMPILE-OK")
print("\nTest: Home kholo. Batches me din + time bhare hon to 'Aaj ki classes' dikhega.")
