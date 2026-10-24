import sqlite3

def _c():
    c = sqlite3.connect("classkhata.db")
    c.execute("CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT)")
    return c

def get(k, default=""):
    c = _c()
    r = c.execute("SELECT v FROM settings WHERE k=?", (k,)).fetchone()
    c.close()
    return r[0] if r else default

def put(k, v):
    c = _c()
    c.execute("INSERT OR REPLACE INTO settings(k, v) VALUES(?,?)", (k, v))
    c.commit()
    c.close()
