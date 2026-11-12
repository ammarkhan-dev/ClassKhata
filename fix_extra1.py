# BatchBook - fix: student page crashed when a student had no pending fee.  Run in ~/classkhata
import os, shutil, sys
p = "studentview.py"
if not os.path.exists(p): sys.exit("NAHI MILA: studentview.py (sahi folder me ho?)")
s = open(p, encoding="utf-8").read()
old = '        _f = (_reg or due)[0]\n        remind = wa_link(s, (_f["baaki"] if _reg else 0) + _xb, _f["due"], _f["y"], _f["m"], lang) if due else ""\n'
new = ('        _f = (_reg or due or [None])[0]\n'
       '        remind = wa_link(s, (_f["baaki"] if _reg else 0) + _xb, _f["due"], _f["y"], _f["m"], lang) if _f else ""\n')
if new in s:
    print("SKIP (pehle se theek hai)")
elif s.count(old) != 1:
    sys.exit("NAHI MILA: remind wali line. Kuch change nahi hua. 'grep -n _f studentview.py' ka output bhejo.")
else:
    n = 1
    while os.path.exists("%s.ext%d" % (p, n)): n += 1
    shutil.copy(p, "%s.ext%d" % (p, n))
    open(p, "w", encoding="utf-8").write(s.replace(old, new)); print("OK studentview.py")
os.system("python -m py_compile studentview.py && echo COMPILE-OK")
