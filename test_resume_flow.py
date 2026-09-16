"""End-to-end check of the LinkedIn-experiences pipeline (offline-safe).

Model: LinkedIn PDF -> experiences (uniform: company, period, role; deduped
on company+date). GitHub -> projects. Resume PDF -> storage only."""
import json
import os
import sys

os.environ.setdefault('TESTING', '1')

from flaskblog import app, routes
from flaskblog.resume_parser import parse_experiences_text

fails = []

def check(name, cond, extra=''):
    print(('PASS' if cond else 'FAIL') + ' - ' + name + (' :: ' + extra if extra and not cond else ''))
    if not cond:
        fails.append(name)

# 1. parser: uniform entries from a LinkedIn-style blob
blob = """
Experience
TechCorp Inc
Software Engineer
Jan 2023 - Present
- Shipped the thing
- Automated all of it
Remote

TechCorp Inc
Jan 2023 - Present
- duplicate of the same role at the same date

Lone Company
March 2026 - March 2026
"""
parsed = parse_experiences_text(blob)
check('parser: uniform keys', all(set(e) == {'company', 'period', 'role'} for e in parsed), str(parsed))
check('parser: dedup same company+date', len(parsed) == 2, str(parsed))
check('parser: role captured', any(e['role'] == 'Software Engineer' for e in parsed), str(parsed))
check('parser: newest first', parsed[0]['company'] == 'Lone Company', str(parsed))
check('parser: location ignored', all('Remote' not in str(e) for e in parsed))
check('parser: details ignored', all('Shipped' not in str(e) for e in parsed))
check('parser: period collapsed', any(e['period'] == 'March 2026' for e in parsed), str(parsed))

# 2. refresh is a no-op (fails soft) when no LinkedIn PDF is stored
with open('content/resume.json', encoding='utf-8') as fh:
    before = fh.read()
real_get = routes.get_document_filename
routes.get_document_filename = lambda key: None  # simulate: nothing stored
stats = routes.refresh_experiences_from_linkedin()
routes.get_document_filename = real_get
check('refresh no-op without stored PDF', stats == {'experiences': 0}, str(stats))
with open('content/resume.json', encoding='utf-8') as fh:
    check('refresh left resume.json untouched', fh.read() == before)

# 3. bundled data is uniform and projects-free
with open('content/resume.json', encoding='utf-8') as fh:
    rj = json.load(fh)
check('resume.json work uniform', all(set(e) == {'company', 'period', 'role'} for e in rj['work']))
check('resume.json has no projects key', 'projects' not in rj)
check('resume.json skills curated', all(s.get('icon') for s in rj['skills']))

# 4. full app render (offline — github fails soft to snapshot)
client = app.test_client()
resp = client.get('/')
check('GET / renders', resp.status_code == 200)
html = resp.get_data(as_text=True)
check('experience view lists company', 'Arkansas Summer Research Institute' in html)
check('experience shows role', 'Student Researcher' in html)
check('no bullet list in experience', 'dm-timeline-item' in html and 'telemetry pipelines' not in html)
check('resume command points at /resume', 'data-resume-url="/resume"' in html)
check('home CV button uses /resume', "window.open('/resume')" in html)

for r in ('/blog', '/admin', '/resume'):
    resp = client.get(r)
    check(f'GET {r}', resp.status_code == 200)

print('---')
print('ALL_PASS' if not fails else f'FAILURES: {len(fails)}')
sys.exit(1 if fails else 0)
