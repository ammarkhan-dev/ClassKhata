# Server owner tool: python reset_password.py "<user name>"   -> prints a temporary password
import sqlite3, sys, secrets
from werkzeug.security import generate_password_hash
if len(sys.argv) < 2:
    sys.exit('Use: python reset_password.py "<user name>"')
c = sqlite3.connect("classkhata.db")
u = c.execute("SELECT id, name FROM users WHERE name=? COLLATE NOCASE", (sys.argv[1].strip(),)).fetchone()
if not u:
    print("User nahi mila. Ye users hain:", [r[0] for r in c.execute("SELECT name FROM users")]); sys.exit(1)
tmp = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(8))
c.execute("UPDATE users SET pw_hash=? WHERE id=?", (generate_password_hash(tmp), u[0])); c.commit()
print("User:", u[1], "| naya temporary password:", tmp, "| login ke baad Account me badal lena")
