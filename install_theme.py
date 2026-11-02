import os,shutil,sys,py_compile
B="templates/base.html"; A='<link rel="stylesheet" href="/static/motion.css?v=1">'; N='<link rel="stylesheet" href="/static/theme.css?v=1">'
if not os.path.exists(B): sys.exit("NAHI MILA: "+B+" (classkhata folder me chalao)")
s=open(B,encoding="utf-8").read()
if "theme.css" in s: print("SKIP: theme pehle se laga hai"); 
elif A not in s: sys.exit("NAHI MILA: motion.css wali line, kuch nahi badla")
else:
    shutil.copy(B,B+".th1"); open(B,"w",encoding="utf-8").write(s.replace(A,A+N,1)); print("OK: base.html me theme jodi")
os.makedirs("static",exist_ok=True); shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)),"static","theme.css"),"static/theme.css"); print("OK: static/theme.css")
