# BatchBook - alag-alag coaching ka alag data.  Run inside ~/classkhata :  python patch_tenant.py
import os, re, shutil, sys

for p in ["app.py", "auth.py", "tenant.py", "classkhata.db"]:
    if not os.path.exists(p):
        sys.exit("NAHI MILA: %s  (sahi folder me ho? cd ~/classkhata)" % p)

def bak(p):
    n = 1
    while os.path.exists("%s.ten%d" % (p, n)):
        n += 1
    shutil.copy(p, "%s.ten%d" % (p, n))

def rd(p):
    return open(p, encoding="utf-8").read()

def wr(p, s):
    open(p, "w", encoding="utf-8").write(s)

# ---- auth.py (sab ya kuch nahi: pehle sab check) ----
a = rd("auth.py")
if "tenant" in a:
    print("SKIP auth.py (pehle se patched)")
else:
    steps = [
        ("import store\n", "import store\nimport tenant\n"),
        ("    c = sqlite3.connect(DB)\n", "    c = tenant.raw_connect(DB)\n"),
        ('            return redirect("/signup" if no_users() else "/login")\n',
         '            return redirect("/signup" if no_users() else "/login")\n'
         '        session.setdefault("tid", session["uid"])\n'),
        ('        if not no_users():\n            return redirect("/login")\n        err, name, inst = None, "", ""\n',
         '        err, name, inst = None, "", ""\n'),
        ('            elif len(pw) < 6:\n',
         '            elif q("SELECT 1 FROM users WHERE name=?", (name,), one=True):\n'
         '                err = "err_taken"\n'
         '            elif len(pw) < 6:\n'),
        ('                store.put("institute", inst)\n                u = q("SELECT * FROM users WHERE name=?", (name,), one=True)\n'
         '                session.permanent = True\n                session.update(uid=u["id"], name=u["name"], lang=lang)\n',
         '                u = q("SELECT * FROM users WHERE name=?", (name,), one=True)\n'
         '                session.permanent = True\n                session.update(uid=u["id"], name=u["name"], lang=lang, tid=u["id"])\n'
         '                store.put("institute", inst)\n'),
        ('                session.update(uid=u["id"], name=u["name"], lang=u["lang"])\n',
         '                session.update(uid=u["id"], name=u["name"], lang=u["lang"], tid=u["id"])\n'),
    ]
    for old, new in steps:
        if a.count(old) != 1:
            sys.exit("NAHI MILA (auth.py): " + old.strip()[:60] + "\nKuch change nahi hua. Mujhe ye line bhej do.")
        a = a.replace(old, new)
    bak("auth.py")
    wr("auth.py", a)
    print("OK auth.py")

# ---- app.py ----
s = rd("app.py")
if "tenant.install" in s:
    print("SKIP app.py (pehle se patched)")
else:
    if not s.startswith("import sqlite3\n"):
        sys.exit("NAHI MILA: app.py pehli line 'import sqlite3' nahi hai. Mujhe app.py ki pehli 5 lines bhej do.")
    bak("app.py")
    wr("app.py", s.replace("import sqlite3\n", "import sqlite3\nimport tenant\ntenant.install()\n", 1))
    print("OK app.py")

# ---- translation for 'name already taken' ----
if not os.path.exists("tr20_en.py"):
    wr("tr20_en.py", 'EN20 = {"err_taken": "This name is already taken. Try another."}\n')
    wr("tr20_hi.py", 'HI20 = {"err_taken": "ये नाम पहले से लिया हुआ है। दूसरा नाम चुनें।"}\n')
    print("OK tr20 files")

# ---- login page link ----
if os.path.exists("templates/login.html"):
    l = rd("templates/login.html")
    if "/signup" in l:
        print("SKIP login.html (link pehle se hai)")
    elif "</form>" in l:
        i = l.rfind("</form>") + len("</form>")
        link = ('\n<p style="text-align:center;margin-top:16px;font-size:14px"><a href="/signup" style="color:#222f40;font-weight:600">'
                "{{ 'नया खाता बनाएँ' if session.get('lang') == 'hi' else 'Create a new account' }}</a></p>")
        bak("templates/login.html")
        wr("templates/login.html", l[:i] + link + l[i:])
        print("OK login.html")
    else:
        print("SKIP login.html: </form> nahi mila. /signup khud kholkar naya account bana sakte ho.")

# ---- .gitignore ----
g = rd(".gitignore") if os.path.exists(".gitignore") else ""
if "data/" not in g:
    wr(".gitignore", g.rstrip("\n") + "\ndata/\n")
    print("OK .gitignore (data/ push nahi hoga)")

# ---- purane account ka data uske naam kar do ----
import sqlite3, tenant
users = sqlite3.connect("classkhata.db").execute("SELECT id, name FROM users").fetchall()
for uid, name in users:
    print("DATA %s (id %d): %s" % (name, uid, "copy ban gayi" if tenant.copy_all(uid) else "pehle se hai"))

os.system("python -m py_compile app.py auth.py tenant.py && echo COMPILE-OK")
print("\nAb app dobara chalao. Do alag browser/incognito se do alag account banakar test karo.")
