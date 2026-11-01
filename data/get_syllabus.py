import requests
from pypdf import PdfReader
from io import BytesIO
from pathlib import Path
import json

base = "https://upmsp.edu.in/Downloads/Syllabus"
files = {
 "10_science": "Class10/931-Science-Class-10.pdf",
 "10_maths": "Class10/928-Maths-Class-10.pdf",
 "10_social_science": "Class10/932-Social-Science-Class-10.pdf",
 "10_english": "Class10/917-English-Class-10.pdf",
 "10_hindi": "Class10/901-Hindi-Class-10.pdf",
 "12_physics": "Class12/151-Physics-Class-12.pdf",
 "12_chemistry": "Class12/152-Chemistry-Class-12.pdf",
 "12_biology": "Class12/153-Biology-Class-12.pdf",
 "12_maths": "Class12/131-Maths-Class-12.pdf",
 "12_english": "Class12/117-English-Class-12.pdf",
 "12_hindi": "Class12/102-General-Hindi-Class-12.pdf",
}
out = {}
for name, path in files.items():
    try:
        r = requests.get(f"{base}/{path}", timeout=30)
        r.raise_for_status()
        pdf = PdfReader(BytesIO(r.content))
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        out[name] = text
        print(f"OK {name}: {len(text)} characters")
    except Exception as e:
        print(f"FAILED {name}: {e}")

Path("data/upmsp/official_text.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("Saved data/upmsp/official_text.json")
