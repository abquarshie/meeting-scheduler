# -*- coding: utf-8 -*-
"""Printable schedule sheets and the data the S-140 filler needs."""
from datetime import date, datetime, timedelta
import io
from pathlib import Path
import re
from xml.sax.saxutils import escape as xml_escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
import streamlit as st

from constants import (
    APP_DIR,
    AUX_HALL,
    EN_WORDS,
    GA_CHARS,
    GA_WORDS,
    HALL_NAMES,
    HALLS,
    MAIN_HALL,
    MIDWEEK,
    ROLE_LABELS,
    ROLE_LABELS_GA,
    SECTION_COLORS,
    SECTION_TITLES,
    STUDENT_ROLES,
    TRANSLATIONS,
    WEEKEND,
)
from db import (
    meeting_rows,
    event_for,
    event_label,
    event_text,
    event_weeks,
    get_meeting_meta,
    get_setting,
    get_talks,
    talk_label,
    talk_text,
)
from parts import SECOND_SPEAKER, TALK_AND_PRAYER
from utils import month_label, fmt_date, week_label, week_start
from workbook import meeting_day

# =============================================================================
# PDF OUTPUT
# =============================================================================
FONT_DIR = APP_DIR / "fonts"
FONT_CANDIDATES = [
    (APP_DIR / "DejaVuSans.ttf", APP_DIR / "DejaVuSans-Bold.ttf"),
    (FONT_DIR / "DejaVuSans.ttf", FONT_DIR / "DejaVuSans-Bold.ttf"),
    (FONT_DIR / "NotoSans-Regular.ttf", FONT_DIR / "NotoSans-Bold.ttf"),
    (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
     Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    (Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"), None),
    (Path("/Library/Fonts/Arial Unicode.ttf"), None),
    (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
]


def _load_font(name, path):
    """Register a TTF only if it has ɛ, ɔ and ŋ."""
    if not path or not path.exists():
        return False
    try:
        font = TTFont(name, str(path))
    except Exception:
        return False
    if not all(ord(c) in font.face.charToGlyph for c in GA_CHARS):
        return False
    pdfmetrics.registerFont(font)
    return True


@st.cache_resource
def register_fonts():
    """Returns (regular, bold, supports_ga)."""
    for regular, bold in FONT_CANDIDATES:
        if _load_font("SlipFont", regular):
            bold_name = "SlipFont-Bold" if _load_font("SlipFont-Bold", bold) else "SlipFont"
            addMapping("SlipFont", 0, 0, "SlipFont")
            addMapping("SlipFont", 1, 0, bold_name)
            addMapping("SlipFont", 0, 1, "SlipFont")
            addMapping("SlipFont", 1, 1, bold_name)
            return "SlipFont", bold_name, True
    return "Helvetica", "Helvetica-Bold", False


SECTION_TITLES_BY_LANG = {
    "English": SECTION_TITLES,
    # Taken from the printed Ga workbook, not translated by hand.
    "Ga": {
        "Opening": "Hiɛkpamɔ",
        "Treasures": "Nyɔŋmɔ Wiemɔ Lɛ Mli Jwetrii",
        "Ministry": "Kasemɔ Bɔ Ni Ashiɛɔ Jogbaŋŋ",
        "Living": "Hii Shi Akɛ Kristofonyo",
        "Closing": "Naamuu",
        "Weekend": "Otsi Naagbee Kpee",
    },
}
ACCENT = colors.HexColor("#24527A")          # the app's ink blue
MUTED = colors.HexColor("#6B7683")
RULE = colors.HexColor("#D7DBE0")


def _lang_name(lang):
    for name, strings in TRANSLATIONS.items():
        if strings is lang:
            return name
    return "English"


# Compact mode never shrinks the type. Two ordinary weeks fit on one A4 at full
# size once the banner stops repeating and the row padding tightens. A week
# with an auxiliary classroom will not: its paired names wrap in the two narrow
# name columns, which makes it about a third taller. Those weeks print one to a
# page rather than being reduced to fit.
COMPACT_ROW_PAD = 1.5
COMPACT_PER_PAGE = 2          # ordinary weeks per sheet; classroom weeks get one


def _sheet_styles(regular, bold, compact=False):
    """One place for the look of the midweek sheet. compact tightens the
    spacing so two weeks share an A4; it never shrinks the type."""
    line = 12 * 0.98 if compact else 12

    def style(name, size, leading, font=regular, **kw):
        return ParagraphStyle(name, fontName=font, fontSize=size, leading=leading, **kw)

    return {
        "title": style("T", 16, 19, bold),
        "cong": style("C", 11, 19, bold, alignment=TA_RIGHT, textColor=MUTED),
        "when": style("W", 11.5, 15, bold, textColor=ACCENT,
                      spaceBefore=5 if compact else 10, spaceAfter=2 if compact else 3),
        "section": style("S", 12, 16, bold),
        "part": style("P", 9, line, leftIndent=11, firstLineIndent=-11),
        "name": style("N", 9, line),
        "label": style("L", 8, line, bold, alignment=TA_RIGHT, textColor=MUTED),
        "_compact": compact,
    }


def clean_value(value):
    """'' for None, NaN and blanks. NaN is truthy, so `or` alone is not enough."""
    if value is None or value != value:
        return ""
    return str(value).strip()


UNFILLED = "\u2014"          # an em dash: nobody assigned yet


def _people(person, assistant):
    """The name, or a dash when the part has nobody.

    A blank cell reads as a fault in the sheet rather than as a part still to
    be filled, and these go up on a noticeboard.
    """
    person, assistant = clean_value(person), clean_value(assistant)
    if person and assistant:
        return f"{person} & {assistant}"
    return person or UNFILLED


def midweek_widths(width):
    """Column widths for the midweek sheet: part, role label, name.

    One set for every week now that the classroom has its own section rather
    than a second name column — which is what used to squeeze the part title
    into a fifth of the page.
    """
    return [width * 0.54, width * 0.13, width * 0.33]


def _song_text(value, words):
    """"Song 74" is stored from an English workbook and "Lala 74" from a Ga one;
    print whichever word matches the sheet."""
    text = clean_value(value)
    if not text:
        return ""
    found = re.search(r"\d+", text)
    return f"{words['song']} {found.group()}" if found else text


def _part_text(part_name, minutes):
    title = clean_value(part_name)
    try:
        mins = int(float(minutes))
    except (TypeError, ValueError):
        mins = None
    if mins and "min" not in title.lower():
        title += f" ({mins} min.)"
    return title


def _banner(meeting_name, congregation, width, st_):
    return Table(
        [[Paragraph(xml_escape(meeting_name), st_["title"]),
          Paragraph(xml_escape(congregation), st_["cong"])]],
        colWidths=[width * 0.62, width * 0.38],
        style=[("LEFTPADDING", (0, 0), (-1, -1), 0),
               ("RIGHTPADDING", (0, 0), (-1, -1), 0),
               ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
               ("LINEBELOW", (0, 0), (-1, -1), 1.4, ACCENT)])


def _midweek_block(rows, meta, lang, st_, width, section_titles, hall_names,
                   role_labels, words):
    """The running order: sections in their workbook colours, songs in place.

    The auxiliary classroom has its own short section at the end rather than a
    second name column beside every student part. The parallel columns put two
    names side by side with nothing on the row saying which room each belonged
    to, and were narrow enough that paired names wrapped. It costs a little
    height, which is affordable now that a classroom week has its own sheet.
    """
    tight = st_.get("_compact")
    row_pad = COMPACT_ROW_PAD if tight else 2.5
    data, style = [], [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), row_pad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), row_pad),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]

    def row(part="", label="", name="", colour=None):
        left = Paragraph(
            (f'<font color="{colour}">\u25cf</font> ' if colour and part else "")
            + xml_escape(part), st_["part"]) if part else ""
        data.append([
            left,
            Paragraph(xml_escape(label), st_["label"]) if label else "",
            Paragraph(xml_escape(name), st_["name"]) if name else ""])

    def section(title, colour):
        data.append([Paragraph(
            f'<font color="{colour}">\u25a0</font>&nbsp;&nbsp;'
            f'<font color="{colour}">{xml_escape(title)}</font>',
            st_["section"]), "", ""])
        i = len(data) - 1
        style.extend([("SPAN", (0, i), (-1, i)),
                      ("TOPPADDING", (0, i), (-1, i), 5 if tight else 10)])

    by_section = {}
    for r in rows.itertuples():
        by_section.setdefault(r.section or "", []).append(r)
    opening = by_section.get("Opening", [])
    closing = by_section.get("Closing", [])
    open_prayer = next((r for r in opening if r.role == "Prayer"), None)
    close_prayer = next((r for r in closing if r.role == "Prayer"), None)
    counselor = next((r for r in opening
                      if r.role == "Aux Classroom Counselor"), None)
    song_colour = SECTION_COLORS.get("Living", "#8A94A0")

    if meta.get("opening_song") or open_prayer is not None:
        row(_song_text(meta.get("opening_song"), words),
            role_labels.get("Prayer", ""),
            (clean_value(open_prayer.person) or UNFILLED)
            if open_prayer is not None else "",
            colour=song_colour)
    for r in opening:
        # the counselor belongs with the classroom's own section below
        if r.role not in ("Prayer", "Aux Classroom Counselor"):
            row("", role_labels.get(r.role, ""), clean_value(r.person) or UNFILLED)

    # the classroom's parts are gathered up front so its section can sit with
    # the field ministry, where those parts belong, rather than at the very end
    classroom = sorted((r for r in rows.itertuples() if r.hall != MAIN_HALL),
                       key=lambda x: int(x.sort_order or 0))

    def classroom_section():
        title = hall_names.get(AUX_HALL, "")
        group = clean_value(meta.get("aux_group"))
        if group:
            title = f"{title} \u2013 {words['group']} {group}"
        colour = SECTION_COLORS.get("Ministry", "#8A94A0")
        section(title, colour)
        if counselor is not None:
            row("", role_labels.get("Aux Classroom Counselor", ""),
                clean_value(counselor.person) or UNFILLED)
        for r in classroom:
            row(_part_text(r.part_name, r.minutes), "",
                _people(r.person, r.assistant), colour=colour)

    shown = False
    for name in ("Treasures", "Ministry", "Living"):
        members = by_section.get(name)
        if not members:
            continue
        colour = SECTION_COLORS.get(name, "#8A94A0")
        section(section_titles.get(name, name), colour)
        if name == "Living" and meta.get("middle_song"):
            row(_song_text(meta["middle_song"], words), colour=song_colour)
        for r in members:
            if r.hall != MAIN_HALL:
                continue
            row("" if r.role == "Reader" else _part_text(r.part_name, r.minutes),
                role_labels.get(r.role, ""), _people(r.person, r.assistant),
                colour=colour)
        if name == "Ministry" and classroom and not shown:
            classroom_section()
            shown = True

    if meta.get("closing_song") or close_prayer is not None:
        row(_song_text(meta.get("closing_song"), words),
            role_labels.get("Prayer", ""),
            (clean_value(close_prayer.person) or UNFILLED)
            if close_prayer is not None else "",
            colour=song_colour)

    if counselor is not None and not classroom:
        row("", role_labels.get("Aux Classroom Counselor", ""),
            clean_value(counselor.person) or UNFILLED)
    elif classroom and not shown:          # no ministry section on this week
        classroom_section()

    table = Table(data, colWidths=midweek_widths(width))
    table.setStyle(TableStyle(style))
    return table


def split_by_type(meetings):
    """(midweek, weekend) from a mixed list, each sorted by date.

    The two sheets are printed separately: they are different documents for
    different people, and nobody wants to pull one apart to hand out.
    """
    ordered = sorted(meetings)
    midweek = [m for m in ordered if m[1] == MIDWEEK]
    weekend = [m for m in ordered if m[1] != MIDWEEK]
    return midweek, weekend


def generate_schedule_pdf(meetings, schedules_df, lang=None, compact=False):
    """The printable schedule: a sheet per midweek meeting (its running
    order), and the weekend meetings together on one landscape table. lang is
    a TRANSLATIONS entry; None means English. compact tightens the midweek
    sheet so two weeks fit on one A4. The weekend sheets hold two months
    each."""
    midweek, weekend = split_by_type(meetings)
    if not midweek:
        return weekend_schedule_pdf(weekend, schedules_df, lang)
    sheet = _midweek_pdf(midweek, schedules_df, lang, compact)
    if not weekend:
        return sheet
    # both kinds asked for at once: midweek pages, then the weekend table
    import pypdf
    out = pypdf.PdfWriter()
    for part in (sheet, weekend_schedule_pdf(weekend, schedules_df, lang)):
        out.append(pypdf.PdfReader(io.BytesIO(part)))
    buffer = io.BytesIO()
    out.write(buffer)
    return buffer.getvalue()


def _midweek_pdf(meetings, schedules_df, lang=None, compact=False):
    """A sheet per midweek meeting: its running order, section by section."""
    lang = lang or TRANSLATIONS["English"]
    name = _lang_name(lang)
    section_titles = SECTION_TITLES_BY_LANG.get(name, SECTION_TITLES)
    role_labels = ROLE_LABELS_GA if name == "Ga" else ROLE_LABELS
    words = GA_WORDS if name == "Ga" else EN_WORDS
    hall_names = {h: lang.get(h, HALL_NAMES.get(h, h)) for h in HALLS}

    regular, bold, _ = register_fonts()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36,
                            topMargin=36, bottomMargin=36)
    st_ = _sheet_styles(regular, bold, compact)
    width = A4[0] - 72
    congregation = get_setting("congregation", "")
    story = []

    def uses_classroom(meeting_date, meeting_type):
        rows = meeting_rows(schedules_df, meeting_date, meeting_type)
        return bool((rows["hall"] != MAIN_HALL).any())

    def sheets(items):
        """Meetings grouped into printed sheets.

        Without compact, one per sheet as before. With it, ordinary midweek
        weeks pair up and a classroom week takes a sheet of its own — at full
        size either way, because shrinking one to fit costs more than the page.
        """
        if not compact:
            # a sheet each unless two-up is asked for: that is what the
            # checkbox is choosing between
            return [[m] for m in items]
        out, current = [], []
        for m in items:
            if m[1] == MIDWEEK and uses_classroom(*m):
                if current:
                    out.append(current)
                    current = []
                out.append([m])
                continue
            current.append(m)
            if len(current) == COMPACT_PER_PAGE:
                out.append(current)
                current = []
        if current:
            out.append(current)
        return out

    for page_number, page_meetings in enumerate(sheets(list(meetings))):
        if page_number:
            story.append(PageBreak())
        banner_shown = None      # each sheet is headed by the meeting name
        for meeting_date, meeting_type in page_meetings:
            rows = meeting_rows(schedules_df, meeting_date, meeting_type)
            if rows.empty:
                continue
            meta = get_meeting_meta(meeting_date, meeting_type)
            midweek = meeting_type == MIDWEEK
            meeting_name = lang.get("midweek_meeting" if midweek else "weekend_meeting",
                                    meeting_type)
            # the meeting name and congregation head the sheet once, not once per
            # week; a document with both kinds gets one banner for each kind
            block = []
            if meeting_name != banner_shown:
                block.append(_banner(meeting_name, congregation, width, st_))
                banner_shown = meeting_name
            heading = clean_value(meta.get("book")) or clean_value(meta.get("heading"))
            when = fmt_date(meeting_date)
            block.append(Paragraph(
                xml_escape(when) + (f"&nbsp;&nbsp;|&nbsp;&nbsp;{xml_escape(heading)}"
                                    if heading else ""), st_["when"]))
            block.append(_midweek_block(rows, meta, lang, st_, width,
                                        section_titles, hall_names, role_labels,
                                        words))
            block.append(Spacer(1, 10 if compact else 18))
            story.append(KeepTogether(block))

    # two versions of a week look identical on a noticeboard otherwise
    story.append(Paragraph(
        xml_escape(f"Prepared {fmt_date(date.today().isoformat())}"),
        ParagraphStyle("Made", fontName=regular, fontSize=7, leading=9,
                       textColor=MUTED, alignment=TA_RIGHT)))
    doc.build(story)
    return buffer.getvalue()


WEEKEND_INK = colors.HexColor("#1F4E5F")      # deep teal, as the printed list
WEEKEND_GREY_HEX = "#6B7280"
WEEKEND_GREY = colors.HexColor(WEEKEND_GREY_HEX)


def weekend_schedule_pdf(meetings, schedules_df, lang=None):
    """The weekend meetings as one continuous landscape document, a row per
    meeting, however many months they span.

    There is one header, at the very top — the congregation, the title and
    the column headings — and the rows then run on down the pages until the
    schedule ends, with nothing repeated or restarted at a page break. A firm
    line with extra space marks where each new month begins. A row is never
    split across two pages. Text and spacing are the same whatever the
    number of months.

    Laid out like the talk schedule the congregation posts: date · chairman ·
    opening prayer · the public talk (theme, speaker) · the Watchtower Study
    (reader). There is no closing prayer column: the speaker says it.
    """
    lang = lang or TRANSLATIONS["English"]
    words = GA_WORDS if _lang_name(lang) == "Ga" else EN_WORDS
    regular, bold, _ = register_fonts()
    meetings = with_event_weekends(m for m in meetings if m[1] != MIDWEEK)

    def style(name, size, font=regular, colour=colors.black, **kw):
        return ParagraphStyle(name, fontName=font, fontSize=size,
                              leading=round(size * 1.3, 1), textColor=colour, **kw)

    st_ = {
        "cong": style("wk_cong", 8.5, bold, WEEKEND_GREY),
        "title": style("wk_title", 20, bold, WEEKEND_INK),
        "head": style("wk_head", 9, bold, WEEKEND_INK),
        "group": style("wk_group", 8, regular, WEEKEND_GREY),
        "date": style("wk_date", 10, bold, WEEKEND_INK),
        "cell": style("wk_cell", 10),
        "event": style("wk_event", 10, bold, WEEKEND_INK),
        "made": style("wk_made", 7.5, regular, WEEKEND_GREY, alignment=TA_RIGHT),
    }
    page = landscape(A4)
    width = page[0] - 72

    congregation = get_setting("congregation", "")
    made = f"Prepared {fmt_date(date.today().isoformat())}"

    # the one header, then one table that flows on across the pages
    story = []
    if congregation:
        story += [Paragraph(xml_escape(congregation.upper()), st_["cong"]),
                  Spacer(1, 2)]
    story += [Paragraph(xml_escape(words["weekend_schedule"]), st_["title"]),
              Spacer(1, 12),
              _weekend_table(meetings, schedules_df, words, st_, width,
                             _lang_name(lang)),
              Spacer(1, 8),
              Paragraph(xml_escape(made), st_["made"])]

    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=page, rightMargin=36, leftMargin=36,
                      topMargin=36, bottomMargin=36).build(story)
    return buffer.getvalue()


EVENT = "event:"     # the meeting type given to an assembly/convention weekend


def with_event_weekends(meetings):
    """The weekend meetings plus, in date order, the weekend of every
    assembly or convention week falling in the same months — as
    (date, "event:assembly") — so the week reads as its label rather than
    simply missing. A meeting saved inside such a week is left out."""
    meetings = [m for m in meetings if not event_for(m[0])]
    months = {d[:7] for d, _ in meetings}
    offset = timedelta(days=meeting_day(WEEKEND))
    for monday, kind in event_weeks().items():
        day = (datetime.strptime(monday, "%Y-%m-%d").date() + offset).isoformat()
        if day[:7] in months:
            meetings.append((day, EVENT + kind))
    return sorted(meetings)


def _weekend_table(meetings, schedules_df, words, st_, width, language="English"):
    """The schedule's table: the column headings once, at the top, then a row
    per meeting, with a divider where a new month begins."""
    def p(text, style_):
        return Paragraph(xml_escape(text), style_)

    years = sorted({d[:4] for d, _ in meetings}) or [str(date.today().year)]
    year = years[0] if len(years) == 1 else f"{years[0]}–{years[-1][2:]}"
    data = [
        [p(year, st_["head"]), p(words["chairman"], st_["head"]),
         p(words["opening_prayer"], st_["head"]), p(words["public_talk"], st_["group"]),
         "", p(words["watchtower"], st_["group"])],
        ["", "", "", p(words["theme"], st_["head"]), p(words["speaker"], st_["head"]),
         p(words["reader"], st_["head"])],
    ]

    def names(rows, keep=lambda r: True):
        found = [_people(r.person, r.assistant) for r in rows.itertuples() if keep(r)]
        return " & ".join(found) if found else UNFILLED

    def is_closing(r):
        return clean_value(r.part_name).lower().startswith("closing")

    month_starts, last_month, event_rows = [], None, []
    for meeting_date, meeting_type in meetings:
        if meeting_type.startswith(EVENT):
            # an assembly or convention weekend: its label across the row
            if last_month and meeting_date[:7] != last_month:
                month_starts.append(len(data))
            last_month = meeting_date[:7]
            day = datetime.strptime(meeting_date, "%Y-%m-%d").date()
            event_rows.append(len(data))
            data.append([p(f"{day:%b} {day.day}", st_["date"]),
                         p(event_text(meeting_type[len(EVENT):], language),
                           st_["event"]),
                         "", "", "", ""])
            continue
        rows = meeting_rows(schedules_df, meeting_date, meeting_type)
        if rows.empty:
            continue
        rows = rows.sort_values("sort_order")
        meta = get_meeting_meta(meeting_date, meeting_type)
        day = datetime.strptime(meeting_date, "%Y-%m-%d").date()
        number = clean_value(meta.get("talk_number"))
        title = clean_value(meta.get("talk_title"))
        theme = " — ".join(b for b in (f"No. {number}" if number else "", title) if b)

        # one talk, however many speakers: a symposium shares the cell
        talk = rows[rows["role"] == "Public Talk"]
        speaker = xml_escape(names(talk))
        if any(clean_value(r.person) and clean_value(getattr(r, "visitor", ""))
               for r in talk.itertuples()):
            speaker += (f'<br/><font size="7.5" color="{WEEKEND_GREY_HEX}">'
                        f'({xml_escape(words["guest_speaker"])})</font>')

        if last_month and meeting_date[:7] != last_month:
            month_starts.append(len(data))      # a new month begins here
        last_month = meeting_date[:7]
        data.append([
            p(f"{day:%b} {day.day}", st_["date"]),
            p(names(rows[rows["role"] == "Weekend Chairman"]), st_["cell"]),
            p(names(rows[rows["role"] == "Prayer"], lambda r: not is_closing(r)),
              st_["cell"]),
            p(theme or UNFILLED, st_["cell"]),
            Paragraph(speaker, st_["cell"]),
            p(names(rows[rows["role"] == "Watchtower Reader"]), st_["cell"]),
        ])

    # the printed list's columns, with the theme given the width it needs for
    # the longest titles to take two lines rather than three — what lets two
    # five-weekend months share a sheet at full size
    grid = [1100, 2050, 2050, 5300, 2800, 2100]     # date fits "May 31" on one line
    table = Table(data, colWidths=[width * g / sum(grid) for g in grid],
                  repeatRows=0)          # headings once, at the very top
    divider = []
    for i in month_starts:
        divider += [
            # a firm line between the months, with room above and below it
            ("LINEABOVE", (0, i), (-1, i), 1.5, WEEKEND_INK),
            ("TOPPADDING", (0, i), (-1, i), 10),
            ("BOTTOMPADDING", (0, i - 1), (-1, i - 1), 9),
        ]
    table.setStyle(TableStyle([
        ("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (1, 1)), ("SPAN", (2, 0), (2, 1)),
    ] + [("SPAN", (1, i), (-1, i)) for i in event_rows] + [
        ("SPAN", (3, 0), (4, 0)),
        ("VALIGN", (0, 0), (-1, 1), "BOTTOM"),
        ("VALIGN", (0, 2), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (3, 0), (-1, 0), 0.5, RULE),
        ("LINEBELOW", (0, 1), (-1, 1), 1.2, WEEKEND_INK),
        ("LINEBELOW", (0, 2), (-1, -1), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ] + divider))
    return table


def build_s140_data(meetings, schedules_df, congregation):
    """Shape saved midweek meetings like the S-140 filler's data.json."""
    weeks, skipped = [], []
    for meeting_date, meeting_type in sorted(meetings):
        rows = meeting_rows(schedules_df, meeting_date, meeting_type)
        meta = get_meeting_meta(meeting_date, meeting_type)
        week = {
            "heading": meta.get("heading") or fmt_date(meeting_date).upper(),
            "chairman": "", "opening_prayer": "", "closing_prayer": "",
            "opening_song": meta.get("opening_song") or "",
            "middle_song": meta.get("middle_song") or "",
            "closing_song": meta.get("closing_song") or "",
            "treasures": [], "ministry": [], "living": [],
        }
        reader = ""
        main_items = {}
        aux_week = bool(meta.get("aux")) or (rows["hall"] != MAIN_HALL).any()
        for _, r in rows.iterrows():
            title = re.sub(r"\s*\(\s*\d+\s*min\.?\s*\)\s*$", "", r["part_name"] or "",
                           flags=re.IGNORECASE)
            item = {"title": title,
                    "min": str(int(r["minutes"])) if pd.notna(r["minutes"]) else "",
                    "name": r["person"] or ""}
            role, section = r["role"], r["section"]
            if r["hall"] != MAIN_HALL:
                target = main_items.get((role, r["part_no"]))
                if target is not None:
                    target["name2"] = item["name"]
                    if r["assistant"]:
                        target["assistant2"] = r["assistant"]
                continue
            if role in STUDENT_ROLES:
                main_items[(role, r["part_no"])] = item
            if role == "Aux Classroom Counselor":
                week["aux_counselor"] = item["name"]
            elif role == "Chairman":
                week["chairman"] = item["name"]
            elif role == "Prayer":
                key = "closing_prayer" if section == "Closing" else "opening_prayer"
                week[key] = item["name"]
            elif role == "Reader":
                reader = item["name"]
            elif role == "Bible Study Conductor":
                week["cbs"] = item
            elif section == "Treasures":
                week["treasures"].append(item)
            elif section == "Ministry":
                if r["assistant"]:
                    item["assistant"] = r["assistant"]
                week["ministry"].append(item)
            elif section == "Living":
                week["living"].append(item)
        if "cbs" in week and reader:
            week["cbs"]["name"] = f"{week['cbs']['name']}/{reader}"
        if "cbs" not in week or len(week["treasures"]) != 3:
            skipped.append(meeting_date)
            continue
        week["aux"] = bool(aux_week)
        week["aux_group"] = clean_value(meta.get("aux_group"))
        weeks.append(week)
    any_aux = any(w["aux"] for w in weeks)
    # "aux" keeps the auxiliary-classroom column (its caption and width)
    return {"congregation": congregation, "weeks": weeks, "aux": any_aux}, skipped


# =============================================================================
# SPEAKER REMINDERS, GUEST LETTERS, ANNUAL TALK CHECKLIST
# (the Public talks page — see talks.py)
# =============================================================================
def co_speakers(schedules_df, meeting_date, meeting_type, person):
    """In a symposium, the other speaker(s) of the same talk; else []."""
    rows = schedules_df[(schedules_df["meeting_date"] == meeting_date)
                        & (schedules_df["meeting_type"] == meeting_type)
                        & (schedules_df["role"] == "Public Talk")]
    return [clean_value(p) for p in rows["person"]
            if clean_value(p) and clean_value(p) != clean_value(person)]


def _part_title(r):
    """How a schedule row's part reads in a message: "5. Making Disciples
    (4 min)", "Chairman", "Public Talk & Closing Prayer" — the speaker says
    the closing prayer; in a symposium the first speaker does, and the second
    has the talk alone (never "…Speaker 2")."""
    if r.role == "Public Talk":
        return ("Public Talk" if clean_value(r.part_name) == SECOND_SPEAKER
                else TALK_AND_PRAYER)
    title = clean_value(r.part_name) or clean_value(r.role)
    minutes = int(r.minutes) if pd.notna(r.minutes) else None
    if minutes and "min" not in title.lower():
        title += f" ({minutes} min)"
    if pd.notna(r.part_no):
        title = f"{int(r.part_no)}. {title}"
    return title


def assignments_between(schedules_df, student_id, start, end):
    """One person's parts from start to end (ISO dates, both included), in
    meeting order.

    Matched on the participant's id, not the printed name, so two people
    with the same name are never merged. Parts where they assist count too:
    the assistant needs to prepare as much as the student.
    """
    dates = schedules_df["meeting_date"].astype(str)
    rows = schedules_df[(dates >= str(start)) & (dates <= str(end))
                        & ((schedules_df["student_id"] == student_id)
                           | (schedules_df["assistant_id"] == student_id))]
    rows = rows.sort_values(["meeting_date", "meeting_type", "sort_order"])
    out = []
    for r in rows.itertuples():
        as_assistant = r.assistant_id == student_id and r.student_id != student_id
        talk, shared = "", []
        if r.role == "Public Talk":
            talk = talk_text(get_meeting_meta(r.meeting_date, r.meeting_type))
            shared = co_speakers(schedules_df, r.meeting_date, r.meeting_type,
                                 r.person)
        hall = r.hall if isinstance(r.hall, str) else MAIN_HALL
        out.append({
            "meeting_date": str(r.meeting_date),
            "meeting_type": r.meeting_type,
            "part": _part_title(r),
            "hall": hall,
            "as_assistant": as_assistant,
            "partner": clean_value(r.person if as_assistant else r.assistant),
            "talk": talk,
            "shared_with": shared,
        })
    return out


def month_assignments_for(schedules_df, student_id, month):
    """One person's parts in a month ("YYYY-MM"), in meeting order."""
    return assignments_between(schedules_df, student_id, f"{month}-01",
                               f"{month}-31")


def _meeting_heading(meeting_date, meeting_type):
    """*Wednesday 14 October* · Midweek meeting — WhatsApp shows *text* bold.

    No calendar emoji: it pictures a fixed date ("JUL 17" on an iPhone) that
    sits misleadingly beside the real one.
    """
    d = datetime.strptime(meeting_date, "%Y-%m-%d").date()
    kind = "Midweek" if meeting_type == MIDWEEK else "Weekend"
    return f"*{d:%A} {d.day} {d:%B}* · {kind} meeting"


def _assignment_lines(items):
    """One person's assignments, grouped under each meeting's heading."""
    lines, current = [], None
    for item in items:
        key = (item["meeting_date"], item["meeting_type"])
        if key != current:
            current = key
            lines += ["", _meeting_heading(*key)]
        line = f"• {item['part']}"
        if item["talk"]:
            line += f" — {item['talk']}"
        if item.get("shared_with"):
            line += " — shared with " + " and ".join(item["shared_with"])
        if item["hall"] != MAIN_HALL:
            line += f" · {HALL_NAMES.get(item['hall'], item['hall'])}"
        if item["as_assistant"]:
            line += (f" — assisting {item['partner']}" if item["partner"]
                     else " — as assistant")
        elif item["partner"]:
            line += f" — with {item['partner']} assisting"
        lines.append(line)
    return lines


def _personal_message(person, gender, period, items):
    """Hello …, the assignments for the period, and a request to say early if
    one can't be taken. Copy-paste only — nothing is sent on the app's behalf."""
    title = "Sister" if gender == "Sister" else "Brother"
    if not items:
        return (f"Hello {title} {person}! You have no meeting assignments "
                f"in {period}.")
    count = len(items)
    return "\n".join(
        [f"Hello {title} {person}! Here are your meeting assignments "
         f"for *{period}*:"]
        + _assignment_lines(items)
        + ["", f"That is {count} assignment{'s' if count != 1 else ''}. "
           "Please let me know as soon as possible if you can't take "
           f"{'any of them' if count != 1 else 'it'}. Thank you!"])


def whatsapp_month_text(person, gender, month, items):
    """A month of one person's assignments as a WhatsApp message."""
    month_name = month_label(month)
    return _personal_message(person, gender, month_name, items)


def week_overview_text(schedules_df, week_of, language="English"):
    """Every assignment in the meeting week (Monday to Sunday), meeting by
    meeting, as the one message sent for that week. A part nobody has yet
    shows "—"."""
    monday = week_start(week_of)
    lines = [f"*Meeting assignments — {week_label(week_of)}*"]
    special = event_label(monday, language)   # in the slip language
    if special:              # an assembly or convention week: no meetings to list
        return "\n".join(lines + ["", special])
    dates = schedules_df["meeting_date"].astype(str)
    rows = schedules_df[(dates >= monday.isoformat())
                        & (dates <= (monday + timedelta(days=6)).isoformat())]
    rows = rows.sort_values(["meeting_date", "meeting_type", "sort_order"])
    for (meeting_date, meeting_type), meeting in rows.groupby(
            ["meeting_date", "meeting_type"], sort=False):
        lines += ["", _meeting_heading(str(meeting_date), meeting_type)]
        talk_done = False
        for r in meeting.itertuples():
            if r.role == "Public Talk":
                if talk_done:
                    continue          # a symposium's speakers share one line
                talk_done = True
                speakers = meeting[meeting["role"] == "Public Talk"]
                who = " & ".join(clean_value(p) for p in speakers["person"]
                                 if clean_value(p)) or UNFILLED
                talk = talk_text(get_meeting_meta(str(meeting_date), meeting_type))
                if len(speakers) > 1:
                    # a symposium: both give the talk, the first says the prayer
                    first = clean_value(speakers.iloc[0]["person"]) or UNFILLED
                    lines.append("• Public Talk" + (f" — {talk}" if talk else "")
                                 + f": {who}")
                    lines.append(f"• Closing Prayer: {first}")
                else:
                    lines.append(f"• {TALK_AND_PRAYER}"
                                 + (f" — {talk}" if talk else "") + f": {who}")
                continue
            hall = r.hall if isinstance(r.hall, str) else MAIN_HALL
            part = _part_title(r)
            if hall != MAIN_HALL:
                part += f" · {HALL_NAMES.get(hall, hall)}"
            who = clean_value(r.person) or UNFILLED
            if clean_value(r.assistant):
                who += f" & {clean_value(r.assistant)}"
            lines.append(f"• {part}: {who}")
    if len(lines) == 1:
        lines.append("No meetings are scheduled that week.")
    return "\n".join(lines)


def _letter_date(iso):
    """'September 26, 2026' — the letter's own convention, distinct from the
    app's day-first fmt_date() used everywhere else."""
    try:
        d = datetime.strptime(str(iso), "%Y-%m-%d").date()
    except ValueError:
        return str(iso)
    return f"{d:%B} {d.day}, {d.year}"


# The two letters share a letterhead and a closing, so they look like one set.
def _letter_styles():
    regular, bold, _ = register_fonts()

    def style(name, size, leading, font=regular, **kw):
        return ParagraphStyle(name, fontName=font, fontSize=size, leading=leading, **kw)

    return {
        "regular": regular, "bold": bold,
        "name": style("ltr_name", 18, 22, bold, alignment=TA_CENTER, textColor=ACCENT),
        "org": style("ltr_org", 13, 17, bold, alignment=TA_CENTER),
        "addr": style("ltr_addr", 8.5, 11, alignment=TA_CENTER, textColor=MUTED),
        "body": style("ltr_body", 10.5, 16),
        "heading": style("ltr_heading", 11, 15, bold, alignment=TA_CENTER),
        "sign": style("ltr_sign", 10.5, 15),
        "cell": style("ltr_cell", 9.5, 13),
        "head_cell": style("ltr_head_cell", 9.5, 13, bold, textColor=colors.white),
    }


def _esc(value):
    return xml_escape(str(value or ""))


def _letterhead(congregation, hall_address, s):
    """Congregation, organisation, address, then today's date."""
    story = [Paragraph(_esc(congregation).upper(), s["name"]),
             Paragraph("CONGREGATION OF JEHOVAH’S WITNESSES", s["org"])]
    if hall_address:
        story.append(Paragraph(_esc(hall_address), s["addr"]))
    return story + [Spacer(1, 22),
                    Paragraph(_esc(_letter_date(date.today().isoformat())), s["body"]),
                    Spacer(1, 20)]


def _contact(signoff, phone, email):
    contact = f"Talk Coordinator - {_esc(signoff)}"
    if phone:
        contact += f"  {_esc(phone)}"
    if email:
        contact += f", {_esc(email)}"
    return contact


def _signature(congregation, signoff, s, gap):
    return [
        Spacer(1, gap),
        Paragraph(f"<i>Your Brothers,</i><br/>"
                  f"{_esc(congregation)} Congregation of Jehovah's Witnesses", s["sign"]),
        Spacer(1, 10),
        HRFlowable(width="50%", thickness=1, color=ACCENT, hAlign="LEFT"),
        Spacer(1, 4),
        Paragraph(f"Talk Coordinator - {_esc(signoff)}", s["sign"]),
    ]


def _letter_bytes(story):
    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, rightMargin=54, leftMargin=54,
                      topMargin=60, bottomMargin=54).build(story)
    return buffer.getvalue()


def invitation_letter_pdf(candidate, congregation, hall_address, meeting_time,
                          signoff, phone="", email=""):
    """A formal request letter to a guest speaker's own congregation, asking
    them to release him for the visit — addressed to his congregation, not to
    him, matching the wording congregations exchange these requests in."""
    s = _letter_styles()
    number = candidate.get("talk_number") or ""
    title = candidate.get("talk_title") or ""
    theme = f"No. {number} {title}".strip() if number else title
    story = _letterhead(congregation, hall_address, s) + [
        Paragraph(_esc(candidate.get("congregation")), s["body"]),
        Spacer(1, 16),
        Paragraph("Dear Brothers,", s["body"]),
        Spacer(1, 6),
        Paragraph("<u>REQUEST FOR PUBLIC SPEAKER</u>", s["heading"]),
        Spacer(1, 10),
        Paragraph("We are writing to request that the brother mentioned below "
                  "visit our congregation to give a public talk.", s["body"]),
        Spacer(1, 12),
        Paragraph(f"Name: {_esc(candidate.get('person'))}<br/>"
                  f"Theme: {_esc(theme)}<br/>"
                  f"Date: {_esc(_letter_date(candidate['meeting_date']))}<br/>"
                  f"Time: {_esc(meeting_time)}", s["body"]),
        Spacer(1, 12),
        Paragraph("We are hopeful that you will take into account and approve "
                  "our request. If you need more information or clarification, "
                  "please feel free to call or send an email.<br/>"
                  + _contact(signoff, phone, email), s["body"]),
        Spacer(1, 12),
        Paragraph("Please accept a warm expression of our Christian love.", s["body"]),
    ] + _signature(congregation, signoff, s, 50)
    return _letter_bytes(story)


def outgoing_speakers_letter_pdf(congregation, hall_address, speakers, signoff,
                                 phone="", email=""):
    """A letter for other congregations listing our approved outgoing
    speakers and the talks each has ready, so they can pick when inviting one.

    speakers: [(name, [(talk_number, talk_title), ...]), ...].
    """
    s = _letter_styles()
    regular, bold = s["regular"], s["bold"]
    story = _letterhead(congregation, hall_address, s) + [
        Paragraph("<u>APPROVED OUTGOING SPEAKERS</u>", s["heading"]),
        Spacer(1, 12),
        Paragraph("Below are the approved outgoing speakers for our "
                  "congregation, and the talks they have prepared. Any "
                  "request should go through the Talk Coordinator before "
                  "the brother is contacted.", s["body"]),
        Spacer(1, 14),
    ]

    # One line per talk. The speaker column is only as wide as the longest
    # name, and the titles get the rest; if a title still won't fit, the talk
    # text shrinks (not below 7.5pt) until every title sits on one line.
    usable = 487                             # A4 minus the letter's 54pt margins
    pad = 8                                  # cell padding, each side
    size = s["cell"].fontSize
    name_w = max([pdfmetrics.stringWidth(n, regular, size) for n, _ in speakers]
                 + [pdfmetrics.stringWidth("Speaker", bold, size)]) + 2 * pad + 2
    name_w = min(name_w, usable * 0.4)
    talk_w = usable - name_w
    lines = [talk_label(number, title) for _, talks in speakers
             for number, title in talks]
    longest = max((pdfmetrics.stringWidth(t, regular, size) for t in lines),
                  default=0)
    room = talk_w - 2 * pad - 2
    if longest > room:
        size = max(7.5, size * room / longest)
    talk_style = ParagraphStyle("ltr_talk", parent=s["cell"], fontSize=size,
                                leading=round(size * 1.37, 1))

    data = [[Paragraph("Speaker", s["head_cell"]),
             Paragraph("Talks prepared", s["head_cell"])]]
    for name, talks in speakers:
        listed = "<br/>".join(_esc(talk_label(n, t)) for n, t in talks) or "—"
        data.append([Paragraph(_esc(name), s["cell"]), Paragraph(listed, talk_style)])
    table = Table(data, colWidths=[name_w, talk_w], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("GRID", (0, 0), (-1, -1), 0.5, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7F9")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), pad),
        ("RIGHTPADDING", (0, 0), (-1, -1), pad),
    ]))
    story.append(table)

    # The closing moves as one block: the signature line on a page by itself,
    # parted from the rest of the letter, is no signature at all.
    story += [Spacer(1, 16), KeepTogether([
        Paragraph("If you need more information or clarification, please "
                  "feel free to call or send an email.<br/>"
                  + _contact(signoff, phone, email), s["body"]),
        Spacer(1, 10),
        Paragraph("Please accept a warm expression of our Christian love.", s["body"]),
    ] + _signature(congregation, signoff, s, 30))]
    return _letter_bytes(story)


def talk_matrix_rows(schedules_df, years):
    """One row per public talk, showing when it was given in each of `years`.

    Every talk in the congregation's list appears, even one never given in
    this window — a blank row is exactly what flags a talk that's overdue,
    and that's the point of the checklist. Reads existing schedule history
    only; nothing is ever deleted.
    """
    talk_rows = schedules_df[(schedules_df["role"] == "Public Talk")
                             & schedules_df["person"].notna()]
    given, titles, seen_meetings = {}, {}, set()
    for r in talk_rows.sort_values("sort_order").itertuples():
        key = (r.meeting_date, r.meeting_type)
        if key in seen_meetings:            # one talk per meeting, even when
            continue                        # a symposium shares it
        seen_meetings.add(key)
        meta = get_meeting_meta(r.meeting_date, WEEKEND)
        number = clean_value(meta.get("talk_number"))
        if not number:
            continue
        title = clean_value(meta.get("talk_title"))
        if title:
            titles[number] = title
        try:
            year = int(str(r.meeting_date)[:4])
        except ValueError:
            continue
        if year in years:
            speakers = " & ".join([r.person] + co_speakers(
                schedules_df, r.meeting_date, r.meeting_type, r.person))
            given.setdefault(number, {}).setdefault(year, []).append(
                (r.meeting_date, speakers))

    talk_titles = dict(get_talks())
    numbers = set(given) | set(talk_titles)

    def sort_key(n):
        try:
            return (0, int(n))
        except ValueError:
            return (1, n)

    rows = []
    for number in sorted(numbers, key=sort_key):
        title = talk_titles.get(number) or titles.get(number, "")
        cells = {year: sorted(given.get(number, {}).get(year, [])) for year in years}
        rows.append({"number": number, "title": title, "years": cells})
    return rows


def talk_checklist_pdf(rows, congregation, years):
    """A printable talk-by-year matrix: a blank cell is a talk that hasn't
    been given that year, so it's safe to assign again."""
    regular, bold, _ = register_fonts()
    title_style = ParagraphStyle("title", fontName=bold, fontSize=14, leading=18)
    sub_style = ParagraphStyle("sub", fontName=regular, fontSize=9, leading=12,
                               textColor=MUTED)
    cell_style = ParagraphStyle("cell", fontName=regular, fontSize=8.5, leading=11)
    empty_style = ParagraphStyle("empty", fontName=regular, fontSize=8.5,
                                 leading=11, textColor=MUTED, alignment=TA_CENTER)

    span = str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}"
    story = [
        Paragraph(xml_escape(f"{congregation} — Public Talk Checklist"), title_style),
        Paragraph(xml_escape(f"Talks given, {span}"), sub_style),
        Spacer(1, 12),
    ]
    data = [["No.", "Title"] + [str(y) for y in years]]
    for r in rows:
        cells = []
        for year in years:
            entries = r["years"].get(year) or []
            if entries:
                text = "<br/>".join(f"{fmt_date(d, short=True)} — {xml_escape(who)}"
                                    for d, who in entries)
                cells.append(Paragraph(text, cell_style))
            else:
                cells.append(Paragraph("—", empty_style))
        data.append([
            r["number"] or "",
            Paragraph(xml_escape(r["title"] or ""), cell_style),
        ] + cells)

    usable = 523                             # A4 minus the 36pt side margins
    fixed = [36, 175]
    year_w = (usable - sum(fixed)) / max(len(years), 1)
    table = Table(data, colWidths=fixed + [year_w] * len(years), repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), bold),
        ("FONTNAME", (0, 1), (-1, -1), regular),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 0), (-1, 0), "CENTER"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("GRID", (0, 0), (-1, -1), 0.5, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7F9")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36,
                            topMargin=36, bottomMargin=36)
    doc.build(story)
    return buffer.getvalue()


