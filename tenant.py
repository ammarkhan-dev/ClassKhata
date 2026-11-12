"""BatchBook multi-institute switch.
Login/sign-up info stays in classkhata.db (users table).  Every logged-in institute's
own data goes to data/t<id>.db.  All existing  sqlite3.connect("classkhata.db")  calls
are redirected automatically while a user is logged in, so no other file needs changes.
"""
import os
import sqlite3

_real = sqlite3.connect
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def raw_connect(*a, **k):
    """Plain sqlite3.connect, never redirected (used for the users table)."""
    return _real(*a, **k)


def path_for(tid):
    return os.path.join(DATA, "t%d.db" % int(tid))


def _make(path):
    """New institute: empty copy of the tables (no rows, no users)."""
    os.makedirs(DATA, exist_ok=True)
    tmp = path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    src = _real("classkhata.db")
    dst = _real(tmp)
    rows = src.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL "
                       "AND name NOT LIKE 'sqlite_%' AND name<>'users' "
                       "ORDER BY type='index'").fetchall()
    for (sql,) in rows:
        try:
            dst.execute(sql)
        except sqlite3.Error:
            pass
    dst.commit()
    src.close()
    dst.close()
    os.replace(tmp, path)


def copy_all(tid):
    """Give institute <tid> a full copy of the current data (used once, for the old account)."""
    p = path_for(tid)
    if os.path.exists(p):
        return False
    os.makedirs(DATA, exist_ok=True)
    src = _real("classkhata.db")
    dst = _real(p)
    src.backup(dst)
    dst.close()
    src.close()
    return True


def install():
    from flask import has_request_context, session

    def _connect(database, *a, **k):
        if str(database) == "classkhata.db" and has_request_context():
            tid = session.get("tid")
            try:
                tid = int(tid) if tid else None
            except (TypeError, ValueError):
                tid = None
            if tid:
                p = path_for(tid)
                if not os.path.exists(p):
                    _make(p)
                return _real(p, *a, **k)
        return _real(database, *a, **k)

    sqlite3.connect = _connect
