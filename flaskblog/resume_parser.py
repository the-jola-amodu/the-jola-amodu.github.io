"""
resume_parser.py — extract WORK EXPERIENCES from an uploaded LinkedIn
profile PDF ("Save to PDF" export). This is the only thing the pipeline
parses, by design:

  LinkedIn PDF  -> experiences   (company, date, role if applicable)
  GitHub        -> projects      (handled by portfolio_data.py)
  Resume PDF    -> storage only  (never parsed)

Entries are uniform and trim: {company, period, role}. Locations and bullet
details are deliberately ignored. FAIL-SOFT: unreadable or empty input
simply yields [], and callers keep whatever they already had.
"""

import os
import re

try:
    from pypdf import PdfReader
    _HAS_PYPDF = True
except Exception:  # noqa: BLE001
    _HAS_PYPDF = False

_BULLET_RE = re.compile(r"^[\u2022\u2023\u25CF\u25E6\u25AA\u00B7\u2013\-*]\s*(.*)$")
_DATE_ITEM = (
    r"(?:"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{1,2}[/-]\d{4}"
    r"|\d{4}"
    r")"
)
_DATE_END = r"(?:" + _DATE_ITEM + r"|present|current|now)"
_DATES_RE = re.compile(
    _DATE_ITEM + r"\s*(?:[–—\-~to]+|to)\s*" + _DATE_END + r"\b",
    re.IGNORECASE,
)
_ORG_HINT = re.compile(
    r"\b(inc|llc|ltd|university|college|institute|school|academy|group|"
    r"technologies?|labs?|co(?:rp)?\.?|corporation|company|center|centre)\b",
    re.IGNORECASE,
)

_SECTION_KEYWORDS = {
    "summary": ["summary", "professional summary", "profile", "about", "about me", "objective"],
    "work": [
        "experience", "work experience", "professional experience",
        "employment", "employment history", "work history", "professional history",
        "professional background", "career",
    ],
    "education": ["education", "academic background", "academics", "schooling", "training"],
    "projects": ["projects", "personal projects", "featured projects", "selected projects", "project experience"],
    "skills": ["skills", "technical skills", "core skills", "top skills", "key skills", "areas of expertise", "tools"],
}


# ---------------------------------------------------------------------------
# PDF -> text
# ---------------------------------------------------------------------------

def extract_pdf_text(path):
    """Read a PDF file and return a normalized single text blob. '' on failure."""
    if not _HAS_PYPDF:
        return ""
    try:
        if not os.path.exists(path):
            return ""
        reader = PdfReader(path)
        parts = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:  # noqa: BLE001
                continue
            parts.append(text)
        return "\n".join(parts)
    except Exception:  # noqa: BLE001
        return ""


def _split_into_lines(text):
    """Return non-empty, stripped lines (bullet prefix kept)."""
    lines = []
    for raw in re.split(r"[\r\n]+", text or ""):
        line = raw.replace("\x00", "").strip()
        if line:
            lines.append(line)
    return lines


def _is_heading(line):
    """True when a line looks like a section heading (short, title-case-ish)."""
    low = line.lower().rstrip(".: ")
    if len(low) > 46 or len(low) < 3:
        return False
    if _DATES_RE.search(line):
        return False
    if re.match(r"^(i\s|we\s|my\s|as\s|with\s)", low):
        return False
    return True


def _find_sections(lines):
    """Map section name -> (start, end) line-index ranges."""
    spans = {}
    heads = []
    for idx, line in enumerate(lines):
        low = line.lower().rstrip(".: -")
        if not _is_heading(line):
            continue
        for section, keys in _SECTION_KEYWORDS.items():
            matched = low in keys or any(
                low.startswith(k) and len(low) < len(k) + 14 for k in keys if len(k) > 3
            )
            if matched:
                heads.append((section, idx))
                break
    heads.sort(key=lambda h: h[1])
    for n, (section, idx) in enumerate(heads):
        end = heads[n + 1][1] if n + 1 < len(heads) else len(lines)
        if section in spans:
            spans[section] = (min(spans[section][0], idx), max(spans[section][1], end))
        else:
            spans[section] = (idx + 1, end)
    return spans


# ---------------------------------------------------------------------------
# Work experience — the ONLY section we parse (LinkedIn is the source of
# truth for experiences; GitHub owns projects; the resume PDF is storage).
# ---------------------------------------------------------------------------

def _clean(text):
    return " ".join(text.split()).strip(" \u00b7\uf0b7\u2022\u2013-")


_STATE_RE = re.compile(r",\s*[A-Z]{2}\s*$")  # "Nashville, TN"
_LOCATION_WORDS = {
    "remote", "hybrid", "onsite", "on-site", "on site",
    "united states", "usa", "u.s.", "canada", "united kingdom", "nigeria",
}
_EMPLOYMENT_TYPE_RE = re.compile(
    r"\s*\((?:internship|full[- ]?time|part[- ]?time|contract|"
    r"freelance|apprenticeship|temporary)\)\s*$",
    re.IGNORECASE,
)
# Page footers, bare durations ("1 year 2 months") and link annotations
# ("(LinkedIn)") are layout noise, never part of an entry.
_JUNK_LINE_RE = re.compile(
    r"^(?:page\s+\d+\s+of\s+\d+"
    r"|\d+\s*(?:years?|months?|yrs?|mos?)\s*(?:\d+\s*(?:months?|mos?)\s*)?"
    r"|\((?:linkedin|personal|website)\))\s*$",
    re.IGNORECASE,
)


def _is_location(line):
    """True for 'City, ST' / 'Greater X Area' / 'Remote' style lines.
    Locations are deliberately excluded from the uniform entry format."""
    line = line.strip()
    if not line or len(line) > 60:
        return False
    if _STATE_RE.search(line):
        return True
    low = line.lower().rstrip(".")
    if low in _LOCATION_WORDS or low.startswith("greater ") or low.endswith(" area"):
        return True
    return False


def _is_titleish(line):
    """A short, non-sentence-looking line can be a company or role line.
    Wrapped description continuations fail this test and are ignored."""
    if not line or len(line) > 80:
        return False
    if line.endswith((".", "!", "?", ",")):
        return False
    if len(line.split()) > 9:
        return False
    if line[0].islower():
        return False
    if _DATES_RE.search(line):
        return False
    return True


def _normalize_period(period):
    """Trim a date range: drop LinkedIn's trailing '(1 month)' style suffix
    and collapse ranges whose start equals the end ('March 2026 - March 2026'
    -> 'March 2026'). Keeps the entry list trim and uniform."""
    p = _clean(period)
    p = re.sub(r"\s*\([^)]*\)\s*$", "", p)
    m = re.match(r"^(.+?\d{4})\s*[\u2013\u2014-]\s*(.+?)$", p)
    if m and m.group(1).strip().lower() == m.group(2).strip().lower():
        p = m.group(1).strip()
    return p.replace("\u00a0", " ")


_MONTH_YEAR_RE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\.?\s+(\d{4})",
    re.IGNORECASE,
)
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"])}


def _period_sort_key(period):
    """Newest-first sort key from the period's start date. Negative values
    keep ascending sorts newest-first and stable for ties; unparseable
    periods sink to the end."""
    m = _MONTH_YEAR_RE.search(str(period))
    if not m:
        return (1, 0, 0)
    return (0, -int(m.group(2)), -_MONTHS[m.group(1)[:3].lower()])


def _sort_experiences(entries):
    """Newest first (by the period's start date); ties keep PDF order."""
    return sorted(entries, key=lambda e: _period_sort_key(e.get("period", "")))


def _split_company_role(title_lines):
    """Uniform (company, role) split. LinkedIn PDFs list the company first
    and the role second; one-liners use 'Role @ Company'. A lone title line
    is the company — the role is simply ignored (if applicable, else keep)."""
    titles = [t for t in title_lines if len(t) < 90]
    if not titles:
        return "", ""
    first = titles[0]
    if "@" in first:
        role, _, company = first.partition("@")
        role, company = role.strip(" -\u2013\u2014"), company.strip()
        if role and company:
            return company, role
    m = re.match(r"^(?P<role>[^@]{1,60}?)\s+at\s+(?P<co>.{1,60})$", first, re.IGNORECASE)
    if m and _ORG_HINT.search(m.group("co")) and not _ORG_HINT.search(m.group("role")):
        return m.group("co").strip(), m.group("role").strip()
    if len(titles) == 1:
        return first, ""
    company, role = first, titles[1]
    if company.strip().lower() == role.strip().lower():
        role = ""
    return (
        _EMPLOYMENT_TYPE_RE.sub("", company).strip(),
        _EMPLOYMENT_TYPE_RE.sub("", role).strip(),
    )


def _parse_experiences(lines):
    """Uniform experience entries: {company, period, role}. Locations, page
    footers, bullet details and wrapped description continuations are all
    ignored on purpose — the display stays trim. LinkedIn lays an entry out
    as Company / Role / date(+duration) / location / bullets, so the last
    two title-ish lines before a date are that entry's (company, role)."""
    entries = []
    pending_title = []
    period = ""

    def flush():
        nonlocal period
        if pending_title and period:
            pair = pending_title[-2:] if len(pending_title) >= 2 else pending_title
            company, role = _split_company_role(pair)
            if company:
                entries.append({
                    "company": company,
                    "period": _normalize_period(period),
                    "role": role,
                })
        pending_title.clear()
        period = ""

    for line in lines:
        if not line:
            continue
        if _DATES_RE.search(line) and not _BULLET_RE.match(line):
            period = line
            flush()  # a date line ends the entry it belongs to
            continue
        if _BULLET_RE.match(line):
            continue  # bullet details: ignored by design
        text = _clean(line)
        if not text or _JUNK_LINE_RE.match(text) or _is_location(text):
            continue
        if not _is_titleish(text):
            continue  # wrapped description continuation: ignored by design
        pending_title.append(text)
    flush()
    return entries


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_experiences_text(text):
    """Parse LinkedIn-profile text into uniform experience entries:
    {company, period, role}. Entries sharing the same company AND date are
    collapsed (LinkedIn repeats an entry per role at the same company)."""
    lines = _split_into_lines(text)
    sections = _find_sections(lines)
    span = sections.get("work")
    if span:
        entries = _parse_experiences(lines[span[0]:span[1]])
    else:
        # No explicit Experience heading: scan the whole text but keep only
        # entries carrying a date, so headers/footers never leak in.
        entries = [e for e in _parse_experiences(lines) if e.get("period")]
    return _sort_experiences(_dedupe_experiences(entries))


def _dedupe_experiences(entries):
    """Same company AND same date = same entry (first occurrence wins)."""
    seen = set()
    out = []
    for entry in entries:
        key = (
            str(entry.get("company", "")).strip().lower(),
            str(entry.get("period", "")).strip().lower(),
        )
        if key in seen or not key[0]:
            continue
        seen.add(key)
        out.append(entry)
    return out
