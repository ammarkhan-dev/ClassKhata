# ClassKhata - sign-up invite code.  Run in ~/classkhata :  python install_invite.py
import os, re, shutil, sys

for p in ["auth.py", "invite.py", "templates/signup.html", "tr21_en.py", "tr21_hi.py"]:
    if not os.path.exists(p):
        sys.exit("NAHI MILA: %s  (sahi folder me ho?)" % p)

def bak(p):
    n = 1
    while os.path.exists("%s.inv%d" % (p, n)):
        n += 1
    shutil.copy(p, "%s.inv%d" % (p, n))

def rd(p): return open(p, encoding="utf-8").read()
def wr(p, s): open(p, "w", encoding="utf-8").write(s)

# ---- auth.py ----
a = rd("auth.py")
if "invite." in a:
    print("SKIP auth.py (pehle se patched)")
else:
    steps = [
        ("import tenant\n", "import tenant\nimport invite\n"),
        ('            elif q("SELECT 1 FROM users WHERE name=?", (name,), one=True):\n',
         '            elif not invite.check(request.form.get("invite", "")):\n                err = "err_invite"\n'
         '            elif q("SELECT 1 FROM users WHERE name=?", (name,), one=True):\n'),
        ('                u = q("SELECT * FROM users WHERE name=?", (name,), one=True)\n                session.permanent = True\n                session.update(uid=u["id"], name=u["name"], lang=lang, tid=u["id"])\n',
         '                u = q("SELECT * FROM users WHERE name=?", (name,), one=True)\n                invite.use(request.form.get("invite", ""), name)\n                session.permanent = True\n                session.update(uid=u["id"], name=u["name"], lang=lang, tid=u["id"])\n'),
    ]
    for old, new in steps:
        if a.count(old) != 1:
            sys.exit("NAHI MILA (auth.py): " + old.strip()[:70] + "\nKuch change nahi hua. Pehle tenant aur account wale patch laga hone chahiye. Ye line mujhe bhej do.")
        a = a.replace(old, new)
    bak("auth.py")
    wr("auth.py", a)
    print("OK auth.py")

# ---- signup.html : invite field cloned from the 'inst' field ----
t = rd("templates/signup.html")
if 'name="invite"' in t:
    print("SKIP signup.html (field pehle se hai)")
else:
    m = re.search(r'(<label\b[^>]*>(?:(?!</label>).)*</label>\s*)?<input\b[^>]*name="inst"[^>]*>', t, re.S)
    if not m:
        print("NOTE: signup.html me 'inst' wala field nahi mila. Mujhe signup.html bhej do, field main jod dunga.")
    else:
        blk = m.group(0)
        new = re.sub(r'\bvalue="[^"]*"', 'value=""', blk)
        new = re.sub(r'name="inst"', 'name="invite" autocapitalize="characters" autocomplete="off"', new)
        new = re.sub(r'\s+required\b', '', new)
        new = re.sub(r'placeholder="[^"]*"', 'placeholder="XXXX-XXXX"', new)
        lab = "{{ 'इन्वाइट कोड' if session.get('lang') == 'hi' else 'Invite code' }}"
        if "<label" in new:
            new = re.sub(r"(<label\b[^>]*>)(?:(?!</label>).)*(</label>)", lambda x: x.group(1) + lab + x.group(2), new, count=1, flags=re.S)
        elif 'placeholder="XXXX-XXXX"' not in new:
            new = new.replace("<input", '<input placeholder="XXXX-XXXX"', 1)
        bak("templates/signup.html")
        wr("templates/signup.html", t[:m.end()] + "\n" + new + t[m.end():])
        print("OK signup.html")

os.system("python -m py_compile auth.py invite.py && echo COMPILE-OK")
print("\nCode banane ke liye:  python invite.py new \"Coaching ka naam\"")
