# ClassKhata - fix: backup routes ka naam /mybackup kiya (more.py ke /backup/download se takra raha tha).  Run in ~/classkhata
import os, shutil, sys

def rd(p): return open(p, encoding="utf-8").read()
def wr(p, s): open(p, "w", encoding="utf-8").write(s)
def bak(p):
    n = 1
    while os.path.exists("%s.bkf%d" % (p, n)):
        n += 1
    shutil.copy(p, "%s.bkf%d" % (p, n))

if not os.path.exists("backup.py"):
    sys.exit("NAHI MILA: backup.py (sahi folder me ho? cd ~/classkhata)")
b = rd("backup.py")
if "/mybackup" in b:
    print("SKIP backup.py (pehle se theek hai)")
else:
    for o, n in (('@app.route("/backup")', '@app.route("/mybackup")'), ('@app.route("/backup/download")', '@app.route("/mybackup/download")'),
                 ("def backup_page(", "def mybackup_page("), ("def backup_download(", "def mybackup_download(")):
        if b.count(o) != 1:
            sys.exit("NAHI MILA (backup.py): %s. Kuch change nahi hua." % o)
        b = b.replace(o, n)
    bak("backup.py"); wr("backup.py", b); print("OK backup.py")

t = "templates/backup.html"
if os.path.exists(t):
    h = rd(t)
    if 'href="/backup/download"' in h:
        bak(t); wr(t, h.replace('href="/backup/download"', 'href="/mybackup/download"')); print("OK", t)
    else:
        print("SKIP", t)

s = "templates/settings.html"
if os.path.exists(s):
    h = rd(s)
    o = '<!--BKP--><a href="/backup"'
    if o in h:
        bak(s); wr(s, h.replace(o, '<!--BKP--><a href="/mybackup"')); print("OK", s)
    else:
        print("SKIP", s)
os.system("python -m py_compile backup.py && echo COMPILE-OK")
