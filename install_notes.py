# ClassKhata - Notes + yaad-dilane wala card on Home.  Run inside ~/classkhata :  python install_notes.py
import os, re, shutil, sys, glob
for p in ["app.py", "notes.py", "templates/ntnotes.html", "templates/home.html"]:
    if not os.path.exists(p): sys.exit("NAHI MILA: %s  (sahi folder me ho? cd ~/classkhata)" % p)
for f in glob.glob("*.py"):
    if f in ("notes.py", "install_notes.py"): continue
    if re.search(r"""route\(\s*['"]/notes""", open(f, encoding="utf-8").read()):
        sys.exit("ROKA: %s me '/notes' pehle se hai. Kuch change nahi hua. Mujhe bata." % f)
def bak(p):
    n = 1
    while os.path.exists("%s.nt%d" % (p, n)): n += 1
    shutil.copy(p, "%s.nt%d" % (p, n))
rd = lambda p: open(p, encoding="utf-8").read()
def wr(p, s): open(p, "w", encoding="utf-8").write(s)

s = rd("app.py")
if "notes.setup" in s: print("SKIP app.py (pehle se juda hai)")
else:
    m = None
    for pat in (r"^todayc\.setup\(.*\)[ \t]*$", r"^kharche\.setup\(.*\)[ \t]*$", r"^backup\.setup\(.*\)[ \t]*$", r"^importer\.setup\(.*\)[ \t]*$"):
        m = re.search(pat, s, re.M)
        if m: break
    if m: pos, add = m.end(), "\nimport notes\nnotes.setup(app)"
    else:
        m = re.search(r'^if __name__\s*==\s*[\'"]__main__[\'"]\s*:', s, re.M)
        if not m: sys.exit("NAHI MILA: app.py me setup ya  if __name__  wali line. Kuch change nahi hua.")
        pos, add = m.start(), "import notes\nnotes.setup(app)\n\n"
    bak("app.py"); wr("app.py", s[:pos] + add + s[pos:]); print("OK app.py")

CARD = '''<!--NT-->{% set _nt = notes_today() %}
<div style="background:#fff;border:1px solid var(--line,#e3e9f0);border-left:4px solid var(--au,#c9a24a);border-radius:20px;padding:16px 18px;margin-bottom:14px;box-shadow:0 2px 12px rgba(34,47,64,.06)">
<div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><b style="font-size:19px;color:var(--navy,#222f40)">{{ _nt.L.title }}</b><a href="/notes" style="background:var(--navy,#222f40);color:#fff;text-decoration:none;font-size:13px;font-weight:600;padding:7px 14px;border-radius:99px">{{ _nt.L.new }}</a></div>
{% for n in _nt["items"] %}<form method="post" action="/notes/{{ n.id }}/done" style="display:flex;align-items:center;gap:10px;padding:11px 0;{% if not loop.first %}border-top:1px solid var(--line,#eef2f7);{% endif %}margin:0">
<input type="hidden" name="next" value="/"><div style="flex:1;min-width:0"><b style="display:block;font-size:15px;overflow-wrap:anywhere">{{ n.text }}</b><span style="font-size:12px;color:{% if n.late %}#b42318{% else %}var(--muted,#6b7686){% endif %}">{{ n.date }}</span></div>
<button style="width:auto;padding:6px 12px;font-size:12px;border-radius:99px;background:#f8f0dc;color:#7a5c14">{{ _nt.L.mark }}</button></form>
{% else %}<div style="padding:10px 0 2px;font-size:14px;color:var(--muted,#6b7686)"><a href="/notes" style="color:inherit;text-decoration:none">{{ _nt.L.all }} ›</a></div>{% endfor %}
<div id="ntEn" style="display:none;margin-top:8px"><button type="button" onclick="Notification.requestPermission().then(function(){location.reload()})" style="font-size:13px;padding:9px;background:#fff;color:var(--navy,#222f40);border:1px solid var(--line,#e3e9f0)">&#128276; {{ _nt.L.enable }}</button></div>
</div>
<script>(function(){try{var it={{ _nt.js|tojson }},day={{ _nt.today|tojson }};
if(!("Notification" in window))return;
if(Notification.permission==="default"){document.getElementById("ntEn").style.display="block";return}
if(Notification.permission!=="granted"||!it.length)return;
it.forEach(function(n){var k="ck_nt_"+n.id+"_"+day;if(localStorage.getItem(k))return;localStorage.setItem(k,"1");
var o={body:n.text,icon:"/static/icon-192.png",tag:"nt"+n.id};
if(navigator.serviceWorker&&navigator.serviceWorker.ready){navigator.serviceWorker.ready.then(function(r){r.showNotification("ClassKhata",o)}).catch(function(){new Notification("ClassKhata",o)})}else{new Notification("ClassKhata",o)}})}catch(e){}})();</script><!--/NT-->
'''
f = "templates/home.html"; h = rd(f)
if "<!--NT-->" in h: print("SKIP home.html (card pehle se hai)")
elif "<!--TC-->" in h:
    bak(f); wr(f, h.replace("<!--TC-->", CARD + "<!--TC-->", 1)); print("OK home.html (Aaj ki classes ke upar)")
else:
    m = re.search(r"\{%\s*block body\s*%\}", h)
    if not m: sys.exit("NAHI MILA: home.html me block body. Kuch aur change nahi hua (app.py ho chuka hoga).")
    bak(f); wr(f, h[:m.end()] + "\n" + CARD + h[m.end():]); print("OK home.html (sabse upar)")
os.system("python -m py_compile app.py notes.py && echo COMPILE-OK")
print("\nTest: Home par 'Notes' card dikhega. + New note se aao, date daalo.")
