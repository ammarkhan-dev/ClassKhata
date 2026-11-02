# ClassKhata - Home me sirf 6 tile: Books hatao, Expenses uski jagah.  Run in ~/classkhata
import os, re, shutil, sys
p = "templates/home.html"
if not os.path.exists(p):
    sys.exit("NAHI MILA: templates/home.html (sahi folder me ho? cd ~/classkhata)")
h = open(p, encoding="utf-8").read()
tiles = list(re.finditer(r'<a\b[^>]*href="/books"[^>]*>.*?</a>[ \t]*\n?', h, re.S))
if not tiles:
    print("SKIP: Books tile pehle se nahi hai")
elif len(tiles) != 1:
    sys.exit("NAHI MILA: Books tile ek se zyada baar mila. Kuch change nahi hua.")
else:
    n = 1
    while os.path.exists("%s.hm%d" % (p, n)): n += 1
    shutil.copy(p, "%s.hm%d" % (p, n))
    h = h[:tiles[0].start()] + h[tiles[0].end():]
    open(p, "w", encoding="utf-8").write(h)
    print("OK: Books tile hata diya")
print("Tiles ab:", re.findall(r'<div class="qi"[^>]*>.*?</div>\s*(?:\{\{[^}]*\}\}|[^<]+)</a>', h, re.S).__len__(), "| Expenses tile:", 'href="/kharche"' in h)
