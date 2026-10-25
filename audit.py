import ast, collections, glob, os, re, shutil, sqlite3, subprocess, sys, traceback
from datetime import datetime
from importlib.metadata import version

SKIP_DIRS = {".git", "__pycache__", "node_modules", "storage", ".cache", ".npm", ".config", ".ssh", ".termux"}
BLOCK_EXT = (".db", ".pyc", ".png", ".jpg", ".gz", ".zip", ".bak")
BLOCK_NAME = {".secret", ".password", "classkhata-report.txt"}
out = []

def p(*a):
    out.append(" ".join(str(x) for x in a))

def head(t):
    out.append("")
    out.append("======== " + t + " ========")

def sh(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return "(error: %s)" % e

def project_files():
    res = []
    for root, dirs, fs in os.walk("."):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(fs):
            if f in BLOCK_NAME or f.endswith(BLOCK_EXT):
                continue
            res.append(os.path.join(root, f)[2:])
    return res

head("ENV")
p("time:", datetime.now().isoformat(timespec="seconds"), "| python:", sys.version.split()[0], "| folder:", os.getcwd())
for mod in ("flask", "werkzeug"):
    try:
        p(mod, version(mod))
    except Exception as e:
        p(mod, "ERROR", e)

head("FILES (path | lines | bytes | modified)")
for f in project_files():
    try:
        b = open(f, "rb").read()
        p(f"{f} | {b.count(10) + 1} | {len(b)} | {datetime.fromtimestamp(os.path.getmtime(f)).strftime('%d %b %H:%M')}")
    except OSError:
        pass

head("GIT")
p(sh("git log --oneline -n 40"))
p("-- status:")
p(sh("git status -s"))
p("-- tracked sensitive files (khali hona chahiye):")
p(sh("git ls-files | grep -E 'secret|password|[.]db$'"))
p("-- .gitignore:")
p(sh("cat .gitignore"))

head("ROUTES (url | methods | endpoint)  [import app]")
sys.path.insert(0, os.getcwd())
try:
    import app as A
    for r in sorted(A.app.url_map.iter_rules(), key=lambda r: r.rule):
        p(f"{r.rule} | {','.join(sorted(r.methods - {'HEAD', 'OPTIONS'}))} | {r.endpoint}")
except Exception:
    p("APP IMPORT FAIL:")
    p(traceback.format_exc())

head("DATABASE (sirf table ka dhancha aur row ginti, koi data nahi)")
try:
    con = sqlite3.connect("file:classkhata.db?mode=ro", uri=True)
    for name, sql in con.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
        n = con.execute('SELECT COUNT(*) FROM "%s"' % name).fetchone()[0]
        p(f"-- {name}: {n} rows")
        p(" ".join((sql or "").split()))
except Exception:
    p(traceback.format_exc())

head("PYTHON FILES (functions@line, routes)")
for f in sorted(glob.glob("*.py")):
    if f in ("audit.py", "patch2.py"):
        continue
    try:
        tree = ast.parse(open(f, encoding="utf-8").read())
    except SyntaxError as e:
        p(f, "SYNTAX ERROR:", e)
        continue
    items = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            decs = [ast.unparse(d) for d in node.decorator_list if "route" in ast.unparse(d) or "before_request" in ast.unparse(d)]
            items.append((node.lineno, node.name + (" " + "; ".join(decs) if decs else "")))
    top = collections.Counter()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            top[node.name] += 1
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    top[t.id] += 1
    p("## " + f)
    p("  " + " | ".join(f"{n}@{l}" for l, n in sorted(items)))
    dup = [n for n, c in top.items() if c > 1]
    if dup:
        p("  DUPLICATE (do baar likhe) names:", ", ".join(dup))

head("TEMPLATES (name | lines | extends | blocks | t-keys)")
used = set()
for f in sorted(glob.glob("templates/*.html")):
    s = open(f, encoding="utf-8").read()
    ext = re.search(r'extends\s+"([^"]+)"', s)
    blocks = re.findall(r"{%\s*block\s+(\w+)", s)
    ks = set(re.findall(r"\bt\(\s*['\"]([A-Za-z0-9_]+)['\"]", s))
    used |= ks
    p(f"{f[10:]} | {s.count(chr(10)) + 1} | {ext.group(1) if ext else '-'} | {','.join(blocks) or '-'} | {len(ks)}")
try:
    import i18n
    en, hi = i18n.TR["en"], i18n.TR["hi"]
    p("translation keys: en", len(en), "| hi", len(hi))
    p("template me use hue par EN me nahi:", sorted(k for k in used if k not in en) or "koi nahi")
    p("template me use hue par HI me nahi:", sorted(k for k in used if k not in hi) or "koi nahi")
    p("EN hai par HI me nahi:", sorted(set(en) - set(hi)) or "koi nahi")
except Exception:
    p(traceback.format_exc())

head("KEY LINES")
p(sh("grep -n -E 'def (fee_history|months_since|pending_all|owed_map|fee_state|ov_get|wa_link|institute|due_date|eligible|parse_d)|/collect|_old_|dd = due_date|baaki = max' fees.py students.py entry.py records.py report.py 2>/dev/null"))

seen = []
for name in ["app.py"] + sys.argv[1:]:
    if name in seen or name in BLOCK_NAME or name.endswith(BLOCK_EXT) or not os.path.isfile(name):
        continue
    seen.append(name)
    head("FULL FILE: " + name)
    for i, line in enumerate(open(name, encoding="utf-8").read().splitlines(), 1):
        p(f"{i:4d}  {line}")

text = "\n".join(out)
open("classkhata-report.txt", "w", encoding="utf-8").write(text)
dest = os.path.expanduser("~/storage/downloads")
if os.path.isdir(dest):
    shutil.copy("classkhata-report.txt", dest)
    print("Report Downloads folder me bhi copy ho gayi.")
print("Report ban gayi: classkhata-report.txt (%d lines). Isse chat me attach kar." % len(text.splitlines()))
