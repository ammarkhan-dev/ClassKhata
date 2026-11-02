# ClassKhata - change password / recovery code / forgot password.  Run in ~/classkhata :  python install_account.py
import os, re, shutil, sys

for p in ["app.py", "auth.py", "account.py", "tenant.py", "templates/account.html", "templates/forgot.html", "templates/recovery_show.html"]:
    if not os.path.exists(p):
        sys.exit("NAHI MILA: %s  (sahi folder me ho? tenant patch laga hai?)" % p)

def bak(p):
    n = 1
    while os.path.exists("%s.acc%d" % (p, n)):
        n += 1
    shutil.copy(p, "%s.acc%d" % (p, n))

def rd(p): return open(p, encoding="utf-8").read()
def wr(p, s): open(p, "w", encoding="utf-8").write(s)

# ---- auth.py ----
a = rd("auth.py")
if '"forgot"' in a:
    print("SKIP auth.py (pehle se patched)")
else:
    steps = [
        ('("login", "signup", "set_lang", "static", "manifest", "sw")', '("login", "signup", "forgot", "set_lang", "static", "manifest", "sw")'),
        ('                store.put("institute", inst)\n                return redirect("/")\n',
         '                store.put("institute", inst)\n                session["rec_pending"] = True\n                return redirect("/account/recovery")\n'),
    ]
    for old, new in steps:
        if a.count(old) != 1:
            sys.exit("NAHI MILA (auth.py): " + old.strip()[:70] + "\nKuch change nahi hua. Ye line mujhe bhej do.")
        a = a.replace(old, new)
    bak("auth.py")
    wr("auth.py", a)
    print("OK auth.py")

# ---- app.py ----
s = rd("app.py")
if "account.setup" in s:
    print("SKIP app.py (pehle se juda hai)")
else:
    m = re.search(r"^library\.setup\(.*\)[ \t]*$", s, re.M) or re.search(r"^syllabus\.setup\(.*\)[ \t]*$", s, re.M)
    if m:
        pos, add = m.end(), "\nimport account\naccount.setup(app)"
    else:
        m = re.search(r'^if __name__\s*==\s*[\'"]__main__[\'"]\s*:', s, re.M)
        if not m:
            sys.exit("NAHI MILA: app.py me library/syllabus setup ya  if __name__  wali line. Kuch change nahi hua.")
        pos, add = m.start(), "import account\naccount.setup(app)\n\n"
    bak("app.py")
    wr("app.py", s[:pos] + add + s[pos:])
    print("OK app.py")

# ---- login.html : forgot link ----
if os.path.exists("templates/login.html"):
    l = rd("templates/login.html")
    if "/forgot" in l:
        print("SKIP login.html (link pehle se hai)")
    elif "</form>" in l:
        i = l.rfind("</form>") + len("</form>")
        link = ('\n<p style="text-align:center;margin-top:14px;font-size:14px"><a href="/forgot" style="color:#222f40;font-weight:600">'
                "{{ 'पासवर्ड भूल गए?' if session.get('lang') == 'hi' else 'Forgot password?' }}</a></p>")
        bak("templates/login.html")
        wr("templates/login.html", l[:i] + link + l[i:])
        print("OK login.html")
    else:
        print("SKIP login.html: </form> nahi mila. /forgot khud kholkar test kar sakte ho.")

# ---- Settings page: 'Account' row, cloned from the neighbour of Log out ----
done = False
for fn in sorted(os.listdir("templates")):
    if not fn.endswith(".html") or fn.startswith(("base", "login", "signup", "forgot", "account")):
        continue
    path = os.path.join("templates", fn)
    t = rd(path)
    if 'href="/account"' in t:
        print("SKIP settings link (pehle se hai)"); done = True; break
    lo = re.search(r'<a\b[^>]*href="/logout"[^>]*>.*?</a>', t, re.S)
    if not lo:
        continue
    prev = [m for m in re.finditer(r'<a\b[^>]*href="(/[^"#]*)"[^>]*>.*?</a>', t[:lo.start()], re.S)]
    if not prev:
        continue
    row = prev[-1].group(0)
    row = re.sub(r'href="/[^"]*"', 'href="/account"', row, count=1)
    key = ('<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
           '<circle cx="8" cy="15" r="4"/><path d="M10.8 12.2 20 3"/><path d="M17 6l3 3"/><path d="M14 9l2 2"/></svg>')
    if re.search(r"<svg\b.*?</svg>", row, re.S):
        row = re.sub(r"<svg\b.*?</svg>", lambda _: key, row, count=1, flags=re.S)
    ex = list(re.finditer(r"\{\{.*?\}\}", row, re.S))
    if not ex:
        continue
    e = ex[-1]
    label = "{{ 'पासवर्ड व रिकवरी कोड' if session.get('lang') == 'hi' else 'Password & recovery code' }}"
    row = row[:e.start()] + label + row[e.end():]
    bak(path)
    wr(path, t[:lo.start()] + row + "\n" + t[lo.start():])
    print("OK settings link in", fn)
    done = True
    break
if not done:
    print("NOTE: Settings me link nahi laga paya. /account seedha kholkar use kar sakte ho (ya mujhe settings wali template bhej do).")

os.system("python -m py_compile app.py auth.py account.py && echo COMPILE-OK")
print("\nApp dobara chalao. Settings me 'Password & recovery code' kholo aur recovery code bana lo.")
