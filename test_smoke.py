"""Smoke test — every public route + medallion/blue-hue wiring."""
import re
import sys

from flaskblog import app
app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True

client = app.test_client()
fails = []

def check(name, cond, extra=''):
    print(('PASS' if cond else 'FAIL') + ' - ' + name + (' :: ' + extra if extra and not cond else ''))
    if not cond:
        fails.append(name)

for route in ('/', '/blog', '/admin', '/resume'):
    resp = client.get(route)
    check(f'GET {route} -> 200', resp.status_code == 200, str(resp.status_code))

# /linkedin redirects to LinkedIn while no PDF is stored
resp = client.get('/linkedin')
check('GET /linkedin -> 302 (no PDF stored)', resp.status_code in (200, 302), str(resp.status_code))

html = client.get('/').get_data(as_text=True)

# medallion: the only toggle between the two sides
check('medallion button present', 'id="dm-medallion"' in html)
check('medallion glyphs present', 'dm-medallion-glyph tech' in html and 'dm-medallion-glyph art' in html)

js = open('flaskblog/static/js/portfolio.js', encoding='utf-8').read()
check('medallion click wired in JS', 'dm-medallion' in js and 'addEventListener' in js)
check('medallion toggles aria-pressed', 'aria-pressed' in js)
check('boot sequence reveals home view', 'bootSequence' in js and 'staggerReveals' in js)

css = open('flaskblog/static/css/portfolio.css', encoding='utf-8').read()
check('blue hue accent', '#58a6ff' in css)
check('blue hue accent-2', '#79c0ff' in css)
check('no leftover green hexes', not re.search(r'#(7ee787|3fb950|196c2e|0d4429)\b', css, re.I))

check('resume command points to /resume', 'data-resume-url="/resume"' in html)
check('linkedin command carries PDF URL', 'data-linkedin-url' in html)

print('---')
print('SMOKE_ALL_PASS' if not fails else f'FAILURES: {len(fails)}')
sys.exit(1 if fails else 0)
