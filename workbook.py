# -*- coding: utf-8 -*-
"""Reading the meeting workbook PDF into weeks and parts."""
import io
import json
import re
import unicodedata

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
# Both editions. With the Ga headings recognised, sections are read from the
# page instead of being guessed from part numbers and durations.
def _heading_re(*variants):
    """Headings wrap across lines in the printed workbook, so every gap between
    words has to match a newline as well as a space."""
    return re.compile(
        "|".join(r"\s+".join(v.split()) for v in variants), re.IGNORECASE)


HEADING_RES = {
    "Treasures": _heading_re(
        "TREASURES FROM GOD", "NY[ƆO]ŊM[ƆO] WIEM[ƆO] L[ƐE] MLI JWETRII"),
    "Ministry": _heading_re(
        "APPLY YOURSELF TO THE FIELD MINISTRY", "KASEM[ƆO] B[ƆO] NI ASHI[ƐE][ƆO]"),
    "Living": _heading_re(
        "LIVING AS CHRISTIANS", "HII SHI AK[ƐE] KRISTOFONYO"),
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
# The page number shares the date line and swaps side with the page: right on
# odd pages, left on even ones. Allow it in front, so week 2 parses like week 1.
DAY_RANGE_RE = re.compile(
    r"^[^\w]*(?:\d{1,3}[ \t]+)?([^\W\d_]{3,})\.?[ \t]+(\d{1,2})[ \t]*["
    + DASHES + r"][ \t]*"
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
    # the printed heading carries the week's reading after a separator,
    # e.g. "SEPTEMBER 7-13 | YEREMIA 32-33". Escaping each dash keeps a
    # literal "-" from being read as a range boundary inside the class.
    lead_chars = r"\s|\u00b7\u2022" + "".join(re.escape(c) for c in DASHES)
    book = re.sub(r"^[" + lead_chars + r"]+", "", line[m.end():])
    # a page number sits right-aligned on the same line, set off by a wide gap
    book = re.sub(r"\s{2,}\d{1,3}\s*$", "", book)
    book = re.sub(r"\s+", " ", book).strip()
    # the printed reading has loose spacing around its dash: "YEREMIA 34 -35"
    book = re.sub(r"\s*([" + DASHES + r"])\s*", r"\1", book)
    book = "" if len(book) > 60 or not re.search(r"\d", book) else book
    return {"label": label, "month": m.group(1), "day": d1, "book": book}


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


# ---------------------------------------------------------------- extraction
# The Ga workbook's fonts carry no Unicode mapping, so a plain text extraction
# returns ɛ ɔ ŋ as ½ Á ¿ and the capitals as control codes — and the codes are
# assigned per font when the file is built, so they differ between faces and
# between months. What does not change is the glyph NAME in each font's
# /Differences array, so the encoding is read out of the PDF itself.
GLYPH_UNICODE = {
    "africanO": "Ɔ", "africanE": "Ɛ", "africanNG": "Ŋ",
    "189lc": "ɛ", "191lc": "ŋ", "193lc": "ɔ",     # named for the code they stand in for
    "tilde": "\u02dc",
}
# the same three letters when they arrive as their stand-in characters
DIRECT = {"\u00bd": "ɛ", "\u00bf": "ŋ", "\u00c1": "ɔ"}
# a modifier letter is printed before the vowel it belongs to: "h ˜aa" is hãa
ACCENTS = [("\u02dc", "\u0303"), ("\u00b4", "\u0301")]


def _font_encodings(pdf_bytes):
    """One {font name: {code: character}} per page.

    Per page, not per document: the same face is subset separately on each
    page, so a code that means Ŋ on one page may be unused or mean something
    else on another. Reusing the first page's table silently drops letters.
    """
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    except Exception:                                      # pragma: no cover
        return []
    pages = []
    for page in reader.pages:
        per_page = {}
        try:
            fonts = page["/Resources"]["/Font"]
        except Exception:
            pages.append(per_page)
            continue
        for ref in list(fonts.values()):
            try:
                font = ref.get_object()
                name = str(font.get("/BaseFont", "")).lstrip("/").split("+")[-1]
                encoding = font.get("/Encoding")
                if encoding is None or isinstance(encoding, str):
                    continue
                differences = encoding.get_object().get("/Differences")
                if not differences:
                    continue
            except Exception:
                continue
            table, code = {}, 0
            for item in differences:
                if isinstance(item, int):
                    code = item
                else:
                    glyph = str(item).lstrip("/")
                    if glyph in GLYPH_UNICODE:
                        table[chr(code)] = GLYPH_UNICODE[glyph]
                    code += 1
            if table:
                per_page.setdefault(name, {}).update(table)
        pages.append(per_page)
    return pages


def _encoding_for(font, encodings):
    """The table for a span's font. PyMuPDF truncates font names to 24
    characters, so an exact lookup misses the longer ones."""
    table = encodings.get(font)
    if table is not None:
        return table
    for name, candidate in encodings.items():
        if name.startswith(font) or font.startswith(name):
            return candidate
    return {}


def _repair(text, font, encodings):
    """Put the Ga letters back. Anything still unmapped below space is an
    ornament from a decorative font (rules, bullets, the music note)."""
    table = _encoding_for(font, encodings)
    text = "".join(table.get(c, c) for c in text)
    text = "".join(DIRECT.get(c, c) for c in text)
    return "".join(c for c in text if ord(c) >= 32)


def _heading_first(lines):
    """Move the week's date line to the top of its page.

    Only the first heading-shaped line is considered, and only when it is not
    already first: a scripture reading on its own line ("YESAIA 5-6") has the
    same shape as a date line, so hoisting a later match would promote the
    reading over the real heading.
    """
    for i, line in enumerate(lines):
        if _heading(line):
            if i == 0:
                return lines
            return [lines[i]] + lines[:i] + lines[i + 1:]
    return lines


def _fix_accents(text):
    for modifier, combining in ACCENTS:
        text = re.sub(r"\s*" + modifier + r"\s*(\w)",
                      lambda m: m.group(1) + combining, text)
    return unicodedata.normalize("NFC", text)


def _pdf_pages(pdf_bytes):
    """One string per page, with the Ga characters repaired.

    PyMuPDF rather than pypdf: it reports the font of every run of text, which
    the repair needs, and pypdf glues words together on this workbook
    ("MLIJWETRII"), which breaks the headings and the part titles.

    The blocks are left in the document's own order, which follows the printed
    columns. Sorting them by position interleaves the two columns, so the part
    numbering looks like it restarts mid-page and one week becomes three. The
    date heading is the one thing out of place — printed at the top, written
    late — so it is moved back to the front of its page afterwards.
    """
    try:
        import pymupdf
    except ImportError:                                    # pragma: no cover
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        return [nfc(page.extract_text() or "") for page in reader.pages]
    per_page = _font_encodings(pdf_bytes)
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for number, page in enumerate(doc):
        encodings = per_page[number] if number < len(per_page) else {}
        lines = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(
                    _repair(sp["text"], sp["font"], encodings) for sp in line["spans"])
                if text.strip():
                    lines.append(_fix_accents(text.rstrip()))
        pages.append("\n".join(_heading_first(lines)))
    return pages


@st.cache_data(show_spinner="Reading workbook…")
def parse_brochure(pdf_bytes):
    """Split the workbook into weeks. A new week starts whenever the part
    numbering restarts; its heading is the first date line before part 1."""
    pages = _pdf_pages(pdf_bytes)
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
        head = heads[g] or {"label": f"Week {g + 1}", "month": None, "day": None,
                            "book": ""}
        label = head["label"]
        if label in weeks:
            label = f"{label} ({g + 1})"
        parts, songs, gaps = _parse_week(text)
        if parts:
            weeks[label] = {"parts": parts, "songs": songs, "gaps": gaps,
                            "text": text.strip(), "month": head["month"],
                            "day": head["day"], "book": head.get("book", "")}
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


def drop_past_weeks(weeks, today=None):
    """Weeks whose last day is still ahead, plus the one we are in.

    Dates have to be assigned first: the whole run is anchored on the first
    week's heading, so the past weeks are what place the future ones. Returns
    (kept, dropped labels). If every week has finished, nothing is dropped —
    an old workbook is more likely a mistake than a request for an empty list.
    """
    today = (today or date.today()).isoformat()
    kept, dropped = {}, []
    for label, w in weeks.items():
        if w.get("end") and w["end"] < today:
            dropped.append(label)
        else:
            kept[label] = w
    if not kept:
        return weeks, []
    return kept, dropped


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


@st.cache_data(show_spinner=False)
def _workbook(schema_name):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT label, data FROM workbook_weeks ORDER BY position").fetchall()
        name = conn.execute(
            "SELECT value FROM settings WHERE key = 'workbook_file'").fetchone()
    return {label: json.loads(data) for label, data in rows}, (name[0] if name else "")


def load_workbook():
    """Read once per run; several pages ask for it more than once."""
    return _workbook(schema())


def _load_workbook_uncached():
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
    _workbook.clear()
    log_change("Workbook saved", f"{file_name or '(removed)'}: {len(weeks)} week(s)")


def parts_summary(parts):
    return [{"No.": p["part_no"], "Title": p["title"],
             "Min": p.get("minutes") or "", "Section": p["section"]}
            for p in parts]
