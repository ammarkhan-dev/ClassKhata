"""BatchBook - import many students at once from CSV / Excel (.xlsx) / pasted rows.
No extra library needed.  Uses the same checks as the Add-student form (students.parse)."""
import csv
import io
import json
import re
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from flask import Response, redirect, render_template, request, session

import students

MAX_ROWS = 500
MAX_BYTES = 2 * 1024 * 1024
COLS = ["name", "cls", "parent_name", "phone", "fee", "adm", "roll", "gender", "address"]
ALIAS = {
    "name": ["name", "student", "student name", "naam", "नाम", "छात्र", "विद्यार्थी", "विद्यार्थी का नाम"],
    "cls": ["class", "cls", "std", "कक्षा", "क्लास"],
    "parent_name": ["parent", "parent name", "father", "father name", "guardian", "parent ka naam", "अभिभावक", "पिता", "पिता का नाम", "अभिभावक का नाम"],
    "phone": ["phone", "mobile", "parent phone", "phone number", "mobile number", "contact", "number", "फोन", "फ़ोन", "मोबाइल", "नंबर", "मोबाइल नंबर"],
    "fee": ["fee", "fees", "monthly fee", "monthly fees", "फीस", "फ़ीस", "मासिक फीस", "मासिक फ़ीस"],
    "adm": ["admission", "admission date", "adm", "adm date", "joining date", "date", "प्रवेश", "प्रवेश तिथि", "दाखिला"],
    "roll": ["roll", "roll no", "roll number", "रोल", "रोल नंबर"],
    "gender": ["gender", "sex", "लिंग"],
    "address": ["address", "पता"],
}
UI = {
    "en": dict(title="Import students", sub="Add many students at once", step1="1. Download the sample", sample="Download sample (CSV)",
               step2="2. Fill it and upload", file="Excel (.xlsx) or CSV file", paste="Or paste rows here", pastehint="Copy rows from Excel / Google Sheets and paste. First row = column names.",
               check="Check", rules="Columns: Name, Class (9-12), Parent name, Parent phone (10 digits), Monthly fee, Admission date. Fee empty = 0. Date empty = today.",
               prev="Check before saving", newn="New students", dupn="Already in app (skipped)", errn="Rows with a problem (skipped)",
               save="Save {n} students", back="Back", row="Row", none_ok="No valid student to save.", done="Done!", added="students added",
               skipped="skipped", view="View students", toomany="Too many rows. Upload at most %d at a time." % MAX_ROWS,
               bad="Could not read the file. Use the sample CSV or an .xlsx file.", empty="Nothing found. Check the file.", big="File is too big (max 2 MB).",
               nm="Name", cl="Class", ph="Phone", fe="Fee", ad="Admission",
               E=dict(err_student_name="Name missing, or class is not 9-12", err_phone="Phone is not 10 digits", err_fee="Fee is not a number",
                      err_date="Date not understood", err_end="Date problem", dup="Same name and phone twice in the file", noname="Name missing")),
    "hi": dict(title="विद्यार्थी इम्पोर्ट", sub="एक साथ कई विद्यार्थी जोड़ें", step1="1. नमूना फ़ाइल डाउनलोड करें", sample="नमूना डाउनलोड (CSV)",
               step2="2. भरकर अपलोड करें", file="Excel (.xlsx) या CSV फ़ाइल", paste="या यहाँ पंक्तियाँ पेस्ट करें", pastehint="Excel / Google Sheets से पंक्तियाँ कॉपी करके पेस्ट करें। पहली पंक्ति = कॉलम के नाम।",
               check="जाँचें", rules="कॉलम: Name, Class (9-12), Parent name, Parent phone (10 अंक), Monthly fee, Admission date। फ़ीस खाली = 0। तारीख खाली = आज।",
               prev="सेव करने से पहले जाँच", newn="नए विद्यार्थी", dupn="पहले से ऐप में हैं (छोड़े गए)", errn="समस्या वाली पंक्तियाँ (छोड़ी गईं)",
               save="{n} विद्यार्थी सेव करें", back="वापस", row="पंक्ति", none_ok="सेव करने लायक कोई सही विद्यार्थी नहीं है।", done="हो गया!", added="विद्यार्थी जुड़े",
               skipped="छोड़े गए", view="विद्यार्थी देखें", toomany="बहुत ज़्यादा पंक्तियाँ। एक बार में अधिकतम %d अपलोड करें।" % MAX_ROWS,
               bad="फ़ाइल पढ़ी नहीं जा सकी। नमूना CSV या .xlsx फ़ाइल इस्तेमाल करें।", empty="कुछ नहीं मिला। फ़ाइल जाँचें।", big="फ़ाइल बहुत बड़ी है (अधिकतम 2 MB)।",
               nm="नाम", cl="कक्षा", ph="फ़ोन", fe="फ़ीस", ad="प्रवेश",
               E=dict(err_student_name="नाम खाली है, या कक्षा 9-12 नहीं है", err_phone="फ़ोन 10 अंकों का नहीं है", err_fee="फ़ीस संख्या नहीं है",
                      err_date="तारीख समझ नहीं आई", err_end="तारीख में समस्या", dup="फ़ाइल में एक ही नाम और फ़ोन दो बार है", noname="नाम खाली है")),
}


class Form(dict):
    """Looks like request.form for students.parse / save_extra."""
    def getlist(self, k):
        return []


def _lg():
    return "hi" if session.get("lang") == "hi" else "en"


def _norm(h):
    return re.sub(r"\s+", " ", str(h or "").strip().lower().replace("_", " ").replace(".", ""))


def _xlsx_rows(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    if sum(i.file_size for i in z.infolist()) > 20 * 1024 * 1024:
        raise ValueError("big")
    names = z.namelist()
    shared = []
    if "xl/sharedStrings.xml" in names:
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root:
            shared.append("".join(t.text or "" for t in si.iter() if t.tag.split("}")[-1] == "t"))
    sheets = sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
    if not sheets:
        raise ValueError("nosheet")
    root = ET.fromstring(z.read(sheets[0]))
    rows = []
    for row in root.iter():
        if row.tag.split("}")[-1] != "row":
            continue
        cells = {}
        for c in row:
            if c.tag.split("}")[-1] != "c":
                continue
            ref = c.get("r", "")
            col = 0
            for ch in re.match(r"[A-Z]+", ref).group(0) if re.match(r"[A-Z]+", ref) else "":
                col = col * 26 + (ord(ch) - 64)
            t = c.get("t")
            val = ""
            for ch in c:
                tag = ch.tag.split("}")[-1]
                if tag == "v" and ch.text is not None:
                    val = shared[int(ch.text)] if t == "s" and ch.text.isdigit() and int(ch.text) < len(shared) else ch.text
                elif tag == "is":
                    val = "".join(x.text or "" for x in ch.iter() if x.tag.split("}")[-1] == "t")
            cells[col - 1] = val
        if cells:
            rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
    return rows


def _csv_rows(data):
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("latin-1")
    return _text_rows(text)


def _text_rows(text):
    first = text.split("\n", 1)[0]
    delim = max([",", "\t", ";"], key=lambda d: first.count(d))
    return [r for r in csv.reader(io.StringIO(text), delimiter=delim)]


def _date(v):
    v = str(v or "").strip()
    if not v:
        return date.today().isoformat()
    if re.fullmatch(r"\d+(\.\d+)?", v) and 20000 < float(v) < 80000:
        return (date(1899, 12, 30) + timedelta(days=int(float(v)))).isoformat()
    for f in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(v[:10] if f.startswith("%Y") else v, f).date().isoformat()
        except ValueError:
            continue
    return v  # parse() will reject it


def _num(v):
    v = re.sub(r"[₹,\s]|rs\.?", "", str(v or "").lower())
    if v == "":
        return "0"
    try:
        return str(int(float(v)))
    except ValueError:
        return v


def _gender(v):
    v = str(v or "").strip().lower()
    if v in ("m", "male", "boy", "लड़का", "पुरुष"):
        return "Male"
    if v in ("f", "female", "girl", "लड़की", "महिला"):
        return "Female"
    return "Other" if v else ""


def _map(rows):
    """-> list of (rownumber, dict) ; header row detected, else fixed column order."""
    rows = [r for r in rows if any(str(x).strip() for x in r)]
    if not rows:
        return []
    idx = {}
    for i, h in enumerate(rows[0]):
        n = _norm(h)
        for k, al in ALIAS.items():
            if n in [_norm(a) for a in al] and k not in idx:
                idx[k] = i
    if "name" in idx:
        body, start = rows[1:], 2
    else:
        idx = {k: i for i, k in enumerate(["name", "cls", "parent_name", "phone", "fee", "adm"])}
        body, start = rows, 1
    out = []
    for n, r in enumerate(body, start):
        d = {k: (str(r[i]).strip() if i < len(r) else "") for k, i in idx.items()}
        out.append((n, d))
    return out


def _clean(d):
    cls = re.search(r"\d+", str(d.get("cls", "")))
    ph = str(d.get("phone", "")).strip()
    if re.fullmatch(r"\d+\.0+", ph):
        ph = ph.split(".")[0]
    if re.fullmatch(r"\d\.\d+[eE]\+?\d+", ph):
        ph = str(int(float(ph)))
    return dict(name=re.sub(r"\s+", " ", d.get("name", "")).strip()[:80], cls=cls.group(0) if cls else "",
                parent_name=d.get("parent_name", "").strip()[:80], phone=ph, fee=_num(d.get("fee", "")),
                adm=_date(d.get("adm", "")), roll=d.get("roll", "").strip()[:12], gender=_gender(d.get("gender", "")),
                address=d.get("address", "").strip()[:200])


def _form(c):
    ses = students.cur_session()
    end = students.default_end(ses)
    if c["adm"] >= end:
        try:
            end = (date.fromisoformat(c["adm"]) + timedelta(days=365)).isoformat()
        except ValueError:
            pass
    return Form(name=c["name"], cls=c["cls"], parent_name=c["parent_name"], phone=c["phone"], fee=c["fee"],
                adm=c["adm"], end=end, ses=ses, roll=c["roll"], gender=c["gender"], address=c["address"])


def _con():
    c = sqlite3.connect("classkhata.db")
    c.row_factory = sqlite3.Row
    return c


def _existing(c):
    out = set()
    for r in c.execute("SELECT name, parent_phone FROM students"):
        out.add((str(r["name"]).strip().lower(), students.digits10(r["parent_phone"] or "") or ""))
    return out


def _check(rows):
    c = _con()
    have = _existing(c)
    c.close()
    good, dups, errs, seen = [], [], [], set()
    for n, d in rows:
        cl = _clean(d)
        if not cl["name"]:
            errs.append((n, cl, "noname")); continue
        v, err = students.parse(_form(cl))
        if err:
            errs.append((n, cl, err)); continue
        key = (cl["name"].lower(), v[3])
        if key in have:
            dups.append((n, cl)); continue
        if key in seen:
            errs.append((n, cl, "dup")); continue
        seen.add(key)
        cl["phone"] = v[3]
        good.append((n, cl))
    return good, dups, errs


def setup(app, db=None):
    @app.route("/students/import")
    def import_page():
        return render_template("import_students.html", L=UI[_lg()], mode="form", msg=request.args.get("m", ""))

    @app.route("/students/import/sample.csv")
    def import_sample():
        txt = ("Name,Class,Parent name,Parent phone,Monthly fee,Admission date\n"
               "Rahul Kumar,10,Suresh Kumar,9876543210,500,2026-04-01\n"
               "Priya Singh,12,Anil Singh,9123456780,800,2026-04-10\n")
        return Response("﻿" + txt, mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=students_sample.csv"})

    @app.route("/students/import/check", methods=["POST"])
    def import_check():
        L = UI[_lg()]
        f = request.files.get("file")
        rows = None
        try:
            if f and f.filename:
                data = f.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    return render_template("import_students.html", L=L, mode="form", msg=L["big"])
                if data[:2] == b"PK":
                    rows = _xlsx_rows(data)
                elif f.filename.lower().endswith(".xls"):
                    raise ValueError("xls")
                else:
                    rows = _csv_rows(data)
            elif request.form.get("paste", "").strip():
                rows = _text_rows(request.form["paste"][:MAX_BYTES])
        except Exception:
            return render_template("import_students.html", L=L, mode="form", msg=L["bad"])
        mapped = _map(rows or [])
        if not mapped:
            return render_template("import_students.html", L=L, mode="form", msg=L["empty"])
        if len(mapped) > MAX_ROWS:
            return render_template("import_students.html", L=L, mode="form", msg=L["toomany"])
        good, dups, errs = _check(mapped)
        payload = json.dumps([c for _n, c in good], ensure_ascii=False)
        return render_template("import_students.html", L=L, mode="preview", good=good, dups=dups, errs=errs, payload=payload)

    @app.route("/students/import/save", methods=["POST"])
    def import_save():
        L = UI[_lg()]
        try:
            items = json.loads(request.form.get("payload", "[]"))[:MAX_ROWS]
            rows = [(i + 1, {k: str(x.get(k, "")) for k in COLS}) for i, x in enumerate(items) if isinstance(x, dict)]
        except (ValueError, AttributeError):
            return redirect("/students/import")
        good, dups, errs = _check(rows)
        c = _con()
        new = "INSERT INTO students(name,cls,parent_name,parent_phone,monthly_fee,admission_date,acad_session,session_end) VALUES(?,?,?,?,?,?,?,?)"
        for _n, cl in good:
            form = _form(cl)
            v, err = students.parse(form)
            if err:
                continue
            cur = c.execute(new, v)
            c.commit()
            students.save_extra(lambda: c, cur.lastrowid, form)
        c.close()
        return render_template("import_students.html", L=L, mode="done", added=len(good), skipped=len(dups) + len(errs))
