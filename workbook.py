# -*- coding: utf-8 -*-
"""Reading the meeting workbook PDF into weeks and parts."""
import io
import json
import re

import pypdf

from parts import *  # noqa: F401,F403


# =============================================================================
# BROCHURE PARSER
# =============================================================================
MONTHS = ("JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|"
          "SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER")
# Week headings are printed in capitals, e.g. "SEPTEMBER 29–OCTOBER 5".
WEEK_RE = re.compile(
    rf"\b(?:{MONTHS})\s+\d{{1,2}}\s*[-–—]\s*(?:(?:{MONTHS})\s+)?\d{{1,2}}\b"
)
# "4. Starting a Conversation (3 min.)" - the duration may sit on the next line.
PART_RE = re.compile(
    r"^[ \t]*(\d{1,2})\.[ \t]+([^\n]{2,90}?)[ \t]*\n?[ \t]*"
    r"\((?:(\d{1,2})[ \t]*min\.?|min\.?[ \t]*(\d{1,2}))\)",
    re.MULTILINE | re.IGNORECASE,
)
SONG_RE = re.compile(r"\b(?:Song|Lala)\s+(\d{1,3})\b", re.IGNORECASE)
HEADING_RES = {
    "Treasures": re.compile(r"TREASURES FROM GOD", re.IGNORECASE),
    "Ministry": re.compile(r"APPLY YOURSELF TO THE FIELD MINISTRY", re.IGNORECASE),
    "Living": re.compile(r"LIVING AS CHRISTIANS", re.IGNORECASE),
}


def _classify(part_no, title, minutes, section):
    if section is None:
        # No English headings found (e.g. another language): guess from numbers.
        if part_no <= 3:
            section = "Treasures"
        elif minutes is not None and minutes >= 30 or "bible study" in title.lower():
            section = "Living"
        else:
            section = None  # decided by the caller
    if section == "Treasures":
        role = {1: "Treasures Talk", 2: "Spiritual Gems"}.get(part_no, "Bible Reading")
    elif section == "Living":
        is_cbs = "bible study" in title.lower() or (minutes or 0) >= 30
        role = "Bible Study Conductor" if is_cbs else "Living Part"
    elif section == "Ministry":
        role = infer_role(title, "Ministry")
        if role not in STUDENT_ROLES:
            role = "Student Talk" if "talk" in title.lower() else "Initial Presentation"
    else:
        role = None
    return section, role


NUM_LINE_RE = re.compile(r"^[ \t]*(\d{1,2})\.[ \t]+(\S.*)$")
DUR_RE = re.compile(r"\((?:(\d{1,2})[ \t]*min\.?|min\.?[ \t]*(\d{1,2}))\)", re.IGNORECASE)


def _clean_title(text):
    return re.sub(r"\s+", " ", text).strip(" .–—-\"“”")


def _find_parts(text):
    """Numbered parts with their minutes. Titles may wrap over up to two lines,
    and the '(N min.)' may sit on the title line or a following line."""
    lines = text.split("\n")
    offsets, pos = [], 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1
    timed, untimed = {}, {}
    for i, line in enumerate(lines):
        m = NUM_LINE_RE.match(line)
        if not m:
            continue
        no = int(m.group(1))
        title_bits, minutes = [], None
        rest = m.group(2)
        for k in range(0, 4):  # this line + up to 3 more
            chunk = rest if k == 0 else lines[i + k] if i + k < len(lines) else None
            if chunk is None or (k > 0 and NUM_LINE_RE.match(chunk)):
                break
            d = DUR_RE.search(chunk)
            if d:
                title_bits.append(chunk[:d.start()])
                minutes = int(d.group(1) or d.group(2))
                break
            title_bits.append(chunk)
        title = _clean_title(" ".join(title_bits) if minutes else m.group(2))
        if not title:
            continue
        entry = (title, minutes, offsets[i])
        if minutes is not None:
            timed.setdefault(no, entry)
        else:
            untimed.setdefault(no, entry)
    if not timed:
        return {}, []
    top = max(timed)
    found = dict(timed)
    for no in range(1, top):  # fill gaps with an untimed numbered line, if any
        if no not in found and no in untimed:
            found[no] = untimed[no]
    gaps = [no for no in range(1, top + 1) if no not in found]
    return found, gaps


def _parse_week(text):
    heading_hits = sorted(
        (m.start(), name) for name, rx in HEADING_RES.items() for m in rx.finditer(text)
    )
    found, gaps = _find_parts(text)
    parts, in_living = [], False
    for part_no in sorted(found):
        title, minutes, pos = found[part_no]
        section = None
        for hpos, name in heading_hits:
            if hpos < pos:
                section = name
        section, role = _classify(part_no, title, minutes, section)
        if section is None:
            # Heuristic: short parts after 3 are student parts until a longer one.
            if not in_living and (minutes or 0) <= 5:
                section = "Ministry"
            else:
                in_living = True
                section = "Living"
            section, role = _classify(part_no, title, minutes, section)
        parts.append(make_slot(title, role, section, part_no, minutes))
    songs = SONG_RE.findall(text)[:3]
    return parts, songs, gaps


# A week heading is a capitalised word plus a day range, e.g. "SEPTEMBER 14-20"
# or the same in Ga. Language-independent: the month word isn't looked up.
# Leading bullets or box-drawing characters are common in exported PDFs, and
# the dash may be any of several. The month word itself is never looked up.
DASHES = "-\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
DAY_RANGE_RE = re.compile(
    r"^[^\w]*([^\W\d_]{3,})\.?[ \t]+(\d{1,2})[ \t]*[" + DASHES + r"][ \t]*"
    r"(?:([^\W\d_]{3,})\.?[ \t]+)?(\d{1,2})\b"
)
ENGLISH_MONTHS = {m: i + 1 for i, m in enumerate(MONTHS.split("|"))}


def _heading(line):
    m = DAY_RANGE_RE.match(line)
    if not m:
        return None
    word = m.group(1)
    # All caps is the usual printed form. A short line starting with a single
    # capitalised word is accepted too, so a workbook that sets its headings in
    # title case still gets a real label instead of "Week 1".
    if not word.isupper() and not (word[:1].isupper() and len(line.strip()) <= 40):
        return None
    d1, d2 = int(m.group(2)), int(m.group(4))
    if not (1 <= d1 <= 31 and 1 <= d2 <= 31):
        return None
    label = f"{m.group(1)} {d1}–" + (f"{m.group(3)} " if m.group(3) else "") + str(d2)
    return {"label": label, "month": m.group(1), "day": d1}


def _timed_part_lines(lines):
    """(line index, part number) for every numbered line that has a duration."""
    out = []
    for i, line in enumerate(lines):
        m = NUM_LINE_RE.match(line)
        if not m:
            continue
        for k in range(0, 4):
            chunk = m.group(2) if k == 0 else (lines[i + k] if i + k < len(lines) else None)
            if chunk is None or (k > 0 and NUM_LINE_RE.match(chunk)):
                break
            if DUR_RE.search(chunk):
                out.append((i, int(m.group(1))))
                break
    return out


@st.cache_data(show_spinner="Reading workbook…")
def parse_brochure(pdf_bytes):
    """Split the workbook into weeks. A new week starts whenever the part
    numbering restarts; its heading is the first date line before part 1."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages = [nfc(page.extract_text() or "") for page in reader.pages]
    lines = "\n".join(pages).split("\n")

    groups, prev = [], None
    for i, no in _timed_part_lines(lines):
        if prev is None or no <= prev:
            groups.append([])
        groups[-1].append(i)
        prev = no

    starts, heads = [], []
    for g, idxs in enumerate(groups):
        zone_start = groups[g - 1][-1] + 1 if g else 0
        head, head_line = None, zone_start
        for j in range(zone_start, idxs[0]):
            h = _heading(lines[j])
            if h:
                # prefer an English month; otherwise the first date-like line
                if h["month"] in ENGLISH_MONTHS or head is None:
                    head, head_line = h, j
                if h["month"] in ENGLISH_MONTHS:
                    break
        starts.append(head_line)
        heads.append(head)

    weeks, empty = {}, []
    for g in range(len(groups)):
        end = starts[g + 1] if g + 1 < len(groups) else len(lines)
        text = "\n".join(lines[starts[g]:end])
        head = heads[g] or {"label": f"Week {g + 1}", "month": None, "day": None}
        label = head["label"]
        if label in weeks:
            label = f"{label} ({g + 1})"
        parts, songs, gaps = _parse_week(text)
        if parts:
            weeks[label] = {"parts": parts, "songs": songs, "gaps": gaps,
                            "text": text.strip(), "month": head["month"],
                            "day": head["day"]}
        else:
            empty.append(label)
    raw = "\n".join(f"--- Page {i + 1} ---\n{t}" for i, t in enumerate(pages))
    return weeks, empty, raw


def guess_first_monday(weeks, file_name=""):
    """Best guess for the Monday the first week starts. Returns (date, sure)."""
    if not weeks:
        return None, False
    first = next(iter(weeks.values()))
    day, month = first.get("day"), first.get("month")
    today = date.today()
    ym = re.search(r"(20\d{2})(0[1-9]|1[0-2])", file_name or "")  # mwb_E_202609.pdf
    if month in ENGLISH_MONTHS and day:
        mnum = ENGLISH_MONTHS[month]
        years = [int(ym.group(1))] if ym else [today.year - 1, today.year, today.year + 1]
        cands = []
        for y in years:
            try:
                cands.append(date(y, mnum, day))
            except ValueError:
                pass
        if cands:
            return min(cands, key=lambda d: abs((d - today).days)), True
    if ym and day:
        try:
            return date(int(ym.group(1)), int(ym.group(2)), day), True
        except ValueError:
            pass
    if day:
        # nearest Monday that falls on that day number
        cands = [today + timedelta(days=n) for n in range(-200, 400)]
        cands = [d for d in cands if d.day == day and d.weekday() == 0]
        if cands:
            return min(cands, key=lambda d: abs((d - today).days)), False
    return today - timedelta(days=today.weekday()), False


def assign_dates(weeks, first_start):
    """Give every week a start/end date, moving forward by whole weeks and
    skipping ahead when a heading's day number shows a week was left out."""
    cur = None
    for w in weeks.values():
        if cur is None:
            cur = first_start
        else:
            cur = cur + timedelta(days=7)
            day = w.get("day")
            if day:
                for _ in range(6):
                    if cur.day == day:
                        break
                    cur += timedelta(days=7)
                else:
                    cur = prev_cur + timedelta(days=7)
        w["start"] = cur.isoformat()
        w["end"] = (cur + timedelta(days=6)).isoformat()
        prev_cur = cur
    return weeks


def week_dates_text(w):
    if not w.get("start"):
        return "no dates"
    s_, e_ = (datetime.strptime(w[k], "%Y-%m-%d").date() for k in ("start", "end"))
    if s_.month == e_.month:
        return f"{s_.day}–{e_.day} {e_:%b %Y}"
    return f"{s_.day} {s_:%b}–{e_.day} {e_:%b %Y}"


def week_for_date(weeks, meeting_date):
    """The workbook week whose date range contains the meeting date."""
    d = str(meeting_date)
    for label, w in weeks.items():
        if w.get("start") and w["start"] <= d <= w["end"]:
            return label
    return None


def load_workbook():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT label, data FROM workbook_weeks ORDER BY position").fetchall()
        name = conn.execute("SELECT value FROM settings WHERE key = 'workbook_file'").fetchone()
    return {label: json.loads(data) for label, data in rows}, (name[0] if name else "")


def save_workbook(weeks, file_name):
    """Weeks must already carry start/end dates (see assign_dates)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM workbook_weeks")
        conn.executemany(
            "INSERT INTO workbook_weeks (label, position, data) VALUES (?, ?, ?)",
            [(label, i, json.dumps(w, ensure_ascii=False))
             for i, (label, w) in enumerate(weeks.items())],
        )
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('workbook_file', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (file_name,))
    log_change("Workbook saved", f"{file_name or '(removed)'}: {len(weeks)} week(s)")


def parts_summary(parts):
    return [{"No.": p["part_no"], "Title": p["title"],
             "Min": p.get("minutes") or "", "Section": p["section"]}
            for p in parts]
