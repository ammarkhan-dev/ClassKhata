# BatchBook - fix: meri backup.html ne teri purani templates/backup.html overwrite kar di thi.  Run in ~/classkhata
import os, shutil, subprocess, sys

def rd(p): return open(p, encoding="utf-8").read()
def wr(p, s): open(p, "w", encoding="utf-8").write(s)
def git(*a):
    r = subprocess.run(["git"] + list(a), capture_output=True, text=True)
    return r.returncode, r.stdout

if not (os.path.exists("backup.py") and os.path.exists("templates/backup.html")):
    sys.exit("NAHI MILA: backup.py ya templates/backup.html (sahi folder me ho? cd ~/classkhata)")
cur = rd("templates/backup.html")
mine = "{{ L.title }}" in cur and "{{ L.why }}" in cur

# 1) save my page under its own name
if mine:
    if not os.path.exists("templates/mybackup.html"):
        wr("templates/mybackup.html", cur); print("OK templates/mybackup.html (meri file ka naya naam)")
else:
    print("NOTE: templates/backup.html me meri file nahi hai (shayad pehle hi theek kar chuke)")

# 2) my route must render mybackup.html
b = rd("backup.py")
if 'render_template("backup.html"' in b:
    n = 1
    while os.path.exists("backup.py.bkg%d" % n): n += 1
    shutil.copy("backup.py", "backup.py.bkg%d" % n)
    wr("backup.py", b.replace('render_template("backup.html"', 'render_template("mybackup.html"')); print("OK backup.py")
else:
    print("SKIP backup.py")

# 3) bring back the original backup.html from git history
if mine:
    code, out = git("log", "--format=%H", "--", "templates/backup.html")
    commits = [c for c in out.split() if c]
    restored = False
    for c in commits:
        code, old = git("show", "%s:templates/backup.html" % c)
        if code == 0 and "{{ L.why }}" not in old and old.strip():
            wr("templates/backup.html", old); restored = True
            print("OK templates/backup.html purani wali wapas aa gayi (commit %s)" % c[:7]); break
    if not restored:
        sys.exit("NAHI MILA: git history me teri purani backup.html nahi mili. Mujhe bata do, main dusra tareeka dunga.")
os.system("python -m py_compile backup.py && echo COMPILE-OK")
