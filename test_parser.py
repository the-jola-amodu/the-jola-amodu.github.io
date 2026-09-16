"""Dev unit test for resume_parser.parse_experiences_text (uniform format)."""
import json

from flaskblog.resume_parser import (
    parse_experiences_text,
    _normalize_period,
    _is_location,
    _period_sort_key,
)

LINKEDIN = """\
Jolaoluwa Amodu
Experience

Alcon
R&D Extern
Aug 2026 - Aug 2026 (1 month)
- Supported R&D externship projects

Break Through Tech
Nashville, TN
AI Studio Fellow
August 2026 - September 2026 (2 months)
- Built FortiFi with Next.js and Tailwind
- Mentorship from Google engineers

PwC
Workflow Automation Extern
February 2025 - March 2025
- Gained hands-on experience with NLP
- Worked with Tesseract OCR

STAIJA
Web Designer
November 2023 - May 2024
- Designed the website from scratch in Figma
"""

out = parse_experiences_text(LINKEDIN)
print(json.dumps(out, indent=2))

checks = []
checks.append(("count", len(out) == 4))
checks.append(("keys uniform", all(set(e) == {"company", "period", "role"} for e in out)))
checks.append(("alcon", out[0]["company"] == "Alcon" and out[0]["role"] == "R&D Extern"))
checks.append(("no location leaked", all("Nashville" not in str(v) for e in out for v in e.values())))
checks.append(("no details leaked", all("FortiFi" not in str(e) for e in out)))
checks.append(("period trimmed", "(1 month)" not in out[0]["period"]))
checks.append(("btt role", out[1]["company"] == "Break Through Tech" and out[1]["role"] == "AI Studio Fellow"))
checks.append(("pwc", out[2]["company"] == "PwC" and out[2]["period"] == "February 2025 - March 2025"))
checks.append(("staija", out[3]["company"] == "STAIJA" and out[3]["role"] == "Web Designer"))

# dedup: the same company + the same date appears only once
dup = LINKEDIN + "\nAlcon\nR&D Extern\nAug 2026 - Aug 2026 (1 month)\n- again\n"
out2 = parse_experiences_text(dup)
checks.append(("dedup same company+date", len(out2) == 4))

# helpers
checks.append(("period collapse", _normalize_period("March 2026 - March 2026 (1 month)") == "March 2026"))
checks.append(("location detected", _is_location("Fort Worth, TX") and _is_location("Remote")))
checks.append(("company not location", not _is_location("STAIJA")))
checks.append(("newest first", _period_sort_key("August 2026 - Present") < _period_sort_key("November 2023 - May 2024")))
checks.append(("undated sinks last", _period_sort_key("") == (1, 0, 0)))
checks.append(("sorted newest first", out[0]["company"] == "Alcon" and out[-1]["company"] == "STAIJA"))

ok = True
for name, passed in checks:
    if not passed:
        ok = False
        print("FAIL:", name)
print("PARSER_ALL_PASS" if ok else "PARSER_SOME_FAILED")
raise SystemExit(0 if ok else 1)