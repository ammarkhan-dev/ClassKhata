# BatchBook - backup.  Run inside ~/classkhata :  python install_backup.py
import os, re, shutil, sys

for p in ["app.py", "backup.py", "backup_daily.py", "tenant.py", "templates/backup.html", "templates/base.html"]:
    if not os.path.exists(p):
        sys.exit("NAHI MILA: %s  (sahi folder me ho? tenant wala patch laga hai?)" % p)

def bak(p):
    n = 1
    while os.path.exists("%s.bkp%d" % (p, n)):
        n += 1
    shutil.copy(p, "%s.bkp%d" % (p, n))

def rd(p): return open(p, encoding="utf-8").read()
def wr(p, s): open(p, "w", encoding="utf-8").write(s)

s = rd("app.py")
if "backup.setup" in s:
    print("SKIP app.py (pehle se juda hai)")
else:
    m = None
    for pat in (r"^kharche\.setup\(.*\)[ \t]*$", r"^importer\.setup\(.*\)[ \t]*$", r"^extra\.setup\(.*\)[ \t]*$", r"^parent\.setup\(.*\)[ \t]*$", r"^absent\.setup\(.*\)[ \t]*$"):
        m = re.search(pat, s, re.M)
        if m:
            break
    if m:
        pos, add = m.end(), "\nimport backup\nbackup.setup(app)"
    else:
        m = re.search(r'^if __name__\s*==\s*[\'"]__main__[\'"]\s*:', s, re.M)
        if not m:
            sys.exit("NAHI MILA: app.py me setup ya  if __name__  wali line. Kuch change nahi hua.")
        pos, add = m.start(), "import backup\nbackup.setup(app)\n\n"
    bak("app.py")
    wr("app.py", s[:pos] + add + s[pos:])
    print("OK app.py")

# backups must never go to GitHub
g = rd(".gitignore") if os.path.exists(".gitignore") else ""
lines = g.split("\n")
add = [x for x in ("backups/", "*.db") if x not in lines]
if add:
    wr(".gitignore", g + ("" if g.endswith("\n") or not g else "\n") + "\n".join(add) + "\n")
    print("OK .gitignore:", " ".join(add))

# link in Settings page
f = "templates/settings.html"
BTN = ('<!--BKP--><a href="/backup" style="display:block;margin:6px 0 12px;padding:12px 14px;border-radius:12px;background:#fff;color:#222f40;'
       'text-decoration:none;font-weight:600;font-size:14px;text-align:center;box-shadow:0 1px 3px rgba(15,23,42,.1)">'
       "{{ 'बैकअप / डेटा डाउनलोड' if session.get('lang') == 'hi' else 'Backup / Download my data' }}</a><!--/BKP-->")
if not os.path.exists(f):
    print("NOTE: templates/settings.html nahi mili. Page seedha /backup par khulta hai.")
else:
    t = rd(f)
    m = re.search(r"\{%\s*block body\s*%\}", t)
    if "<!--BKP-->" in t:
        print("SKIP settings.html (link pehle se hai)")
    elif not m:
        print("NOTE: settings.html me block body nahi mila. Page seedha /backup par kholo.")
    else:
        bak(f)
        wr(f, t[:m.end()] + "\n" + BTN + t[m.end():])
        print("OK settings.html")

os.system("python -m py_compile app.py backup.py backup_daily.py && echo COMPILE-OK")
print("\nTest: python backup_daily.py   (backups/ folder bananaa chahiye)")
