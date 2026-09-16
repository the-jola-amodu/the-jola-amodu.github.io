"""Full end-to-end: upload PDFs through /admin under the new model ->
LinkedIn rebuilds experiences only (uniform, deduped), resume is
storage-only -> homepage sections repopulated. Cleans up afterwards."""
import io
import json
import os
import sys

os.environ.setdefault('TESTING', '1')

RESUME_JSON = os.path.join('content', 'resume.json')
with open(RESUME_JSON, 'r', encoding='utf-8') as fh:
    RESUME_BACKUP = fh.read()

fails = []

def check(name, cond, extra=''):
    print(('PASS' if cond else 'FAIL') + ' - ' + name + (' :: ' + extra if extra and not cond else ''))
    if not cond:
        fails.append(name)


def build_pdf(lines):
    """Minimal single-page PDF with Helvetica text lines."""
    content = io.BytesIO()
    content.write(b"BT /F1 12 Tf 16 TL 72 720 Td\n")
    for i, line in enumerate(lines):
        esc = line.replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)')
        if i:
            content.write(b"T*\n")
        content.write(f"({esc}) Tj\n".encode('latin-1'))
    content.write(b"ET")
    stream = content.getvalue()

    objs = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>")
    objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(f"{n} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objs)+1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(b"trailer << /Size " + str(len(objs)+1).encode() +
              b" /Root 1 0 R >>\nstartxref\n" + str(xref_pos).encode() + b"\n%%EOF")
    return out.getvalue()


LINKEDIN_LINES = [
    "Jolaoluwa Amodu",
    "Experience",
    "Nova Robotics Lab",
    "Systems Engineer",
    "Jun 2024 - Present",
    "1 yr 3 mos",
    "Remote",
    "- Built telemetry pipelines",
    "Nova Robotics Lab",
    "Systems Engineer",
    "Jun 2024 - Present",
    "1 yr 3 mos",
    "Remote",
    "- duplicate shown twice on LinkedIn",
    "PwC",
    "Workflow Automation Extern",
    "February 2025 - March 2025",
    "2 mos",
    "Lagos, Nigeria",
    "- NLP externship work",
]

from flaskblog import app
app.config['WTF_CSRF_ENABLED'] = False

from flaskblog.resume_parser import extract_pdf_text
pdf_bytes = build_pdf(LINKEDIN_LINES)
with open('_tmp_probe.pdf', 'wb') as fh:
    fh.write(pdf_bytes)
text = extract_pdf_text('_tmp_probe.pdf')
os.remove('_tmp_probe.pdf')
check('pdf built & readable by pypdf', 'Nova Robotics Lab' in text)

client = app.test_client()
docs_dir = os.path.join('flaskblog', 'static', 'assets', 'documents')
_before = set(os.listdir(docs_dir))

# Snapshot the DB rows this test is about to touch. There is exactly one
# row per doc_key, so uploading a probe REPLACES the owner's real record;
# cleanup must restore what was there, not just delete the probe.
from flaskblog import get_db_connection
conn = get_db_connection()
cur = conn.cursor()
cur.execute("SELECT doc_key, filename FROM documents WHERE doc_key IN ('resume_pdf','linkedin_pdf');")
_DOCS_BEFORE = cur.fetchall()
cur.execute("SELECT content FROM resume_data WHERE doc_key = 'linkedin_experiences';")
_row = cur.fetchone()
_EXP_BEFORE = _row[0] if _row else None
conn.commit()
cur.close()
conn.close()

# -- upload through the LINKEDIN card -> experiences rebuilt --
resp = client.post('/admin', data={
    'linkedin_pdf': (io.BytesIO(pdf_bytes), 'linkedin_probe.pdf'),
    'submit': 'Upload LinkedIn PDF',
}, content_type='multipart/form-data', follow_redirects=False)
check('linkedin card POST accepted (302)', resp.status_code == 302, str(resp.status_code))

with open(RESUME_JSON, 'r', encoding='utf-8') as fh:
    merged = json.load(fh)
work = merged.get('work', [])
check('work entries uniform', all(set(w) == {'company', 'period', 'role'} for w in work), str(work))
check('resume.json work rebuilt from LinkedIn', any(w['company'] == 'Nova Robotics Lab' for w in work), str(work))
check('duplicate company+date collapsed', len(work) == 2, str(work))
check('role captured', any(w['company'] == 'Nova Robotics Lab' and w['role'] == 'Systems Engineer' for w in work), str(work))
check('duration junk dropped', all('mos' not in w['period'] for w in work), str([w['period'] for w in work]))
check('location dropped', all('remote' not in str(v).lower() and 'lagos' not in str(v).lower() for w in work for v in w.values()))
check('details dropped', all('telemetry' not in str(v).lower() for w in work for v in w.values()))

# -- upload through the RESUME card -> storage only --
resp = client.post('/admin', data={
    'resume_pdf': (io.BytesIO(pdf_bytes), 'resume_probe.pdf'),
    'submit': 'Upload Resume',
}, content_type='multipart/form-data', follow_redirects=False)
check('resume card POST accepted (302)', resp.status_code == 302, str(resp.status_code))
with open(RESUME_JSON, 'r', encoding='utf-8') as fh:
    after_resume = json.load(fh)
check('resume upload did NOT touch experiences', after_resume.get('work') == merged.get('work'))

# -- /resume and /linkedin serve the uploaded PDFs --
resp = client.get('/resume')
check('/resume serves uploaded PDF', resp.status_code == 200 and resp.data[:5] == b'%PDF-', str(resp.status_code))
resp = client.get('/linkedin')
check('/linkedin serves uploaded PDF', resp.status_code == 200 and resp.data[:5] == b'%PDF-', str(resp.status_code))

# -- homepage: experiences come from the LinkedIn upload --
html = client.get('/').get_data(as_text=True)
check('experience view shows PDF company', 'Nova Robotics Lab' in html)
check('experience view shows PDF role', 'Systems Engineer' in html)

# -- cleanup: restore resume.json + DB records + files --
with open(RESUME_JSON, 'w', encoding='utf-8') as fh:
    fh.write(RESUME_BACKUP)

from flaskblog import get_db_connection
conn = get_db_connection()
cur = conn.cursor()
# Restore the DB exactly as it was found: the owner's real document rows
# and any stored experiences snapshot go back, the probe rows go away.
cur.execute("DELETE FROM documents WHERE doc_key IN ('resume_pdf','linkedin_pdf');")
for key, filename in _DOCS_BEFORE:
    cur.execute(
        "INSERT INTO documents (doc_key, filename) VALUES (%s, %s);",
        (key, filename),
    )
cur.execute("DELETE FROM resume_data WHERE doc_key = 'linkedin_experiences';")
if _EXP_BEFORE is not None:
    cur.execute(
        "INSERT INTO resume_data (doc_key, content) VALUES (%s, %s);",
        ('linkedin_experiences', _EXP_BEFORE),
    )
conn.commit()
cur.close()
conn.close()

import gc
import time

added = [fn for fn in os.listdir(docs_dir) if fn not in _before]
for attempt in range(6):
    try:
        for fn in added:
            path = os.path.join(docs_dir, fn)
            if os.path.exists(path):
                os.remove(path)
        if not [fn for fn in added if os.path.exists(os.path.join(docs_dir, fn))]:
            break
    except PermissionError:
        gc.collect()
        time.sleep(0.5)
leftover = [fn for fn in added if os.path.exists(os.path.join(docs_dir, fn))]
if leftover:
    print('WARN - probe files locked by Windows, remove manually:', leftover)
else:
    print('PASS - cleanup removed probe PDFs')

html = client.get('/').get_data(as_text=True)
check('homepage back to bundled experience data', 'Nova Robotics Lab' not in html)

print('---')
print('ALL_PASS' if not fails else f'FAILURES: {len(fails)}')
sys.exit(1 if fails else 0)
