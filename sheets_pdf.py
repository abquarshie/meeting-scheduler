# -*- coding: utf-8 -*-
"""Printable schedule sheets and the data the S-140 filler needs."""
import io
import re
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)

from workbook import *  # noqa: F401,F403


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


def _sheet_styles(regular, bold, compact=False, scale=None):
    """One place for the look of both sheets.

    compact squeezes a midweek week to about two thirds of its height so two
    fit on one A4. Everything shrinks together — type, leading and padding —
    because taking it out of any one of them alone shows.
    """
    k = 1.0                       # compact tightens spacing, never the type
    return {
        "title": ParagraphStyle("T", fontName=bold, fontSize=16 * k,
                                leading=19 * k),
        "cong": ParagraphStyle("C", fontName=bold, fontSize=11 * k,
                               leading=19 * k, alignment=TA_RIGHT, textColor=MUTED),
        "when": ParagraphStyle("W", fontName=bold, fontSize=11.5 * k,
                               leading=15 * k, textColor=ACCENT,
                               spaceBefore=5 if compact else 10,
                               spaceAfter=2 if compact else 3),
        "section": ParagraphStyle("S", fontName=bold, fontSize=12 * k,
                                  leading=16 * k),
        "part": ParagraphStyle("P", fontName=regular, fontSize=9 * k,
                               leading=(12 * k * 0.98 if compact else 12),
                               leftIndent=11, firstLineIndent=-11),
        "name": ParagraphStyle("N", fontName=regular, fontSize=9 * k,
                               leading=(12 * k * 0.98 if compact else 12)),
        "label": ParagraphStyle("L", fontName=bold, fontSize=8 * k,
                                leading=(12 * k * 0.98 if compact else 12),
                                alignment=TA_RIGHT, textColor=MUTED),
        "sub": ParagraphStyle("U", fontName=bold, fontSize=7 * k, leading=9 * k,
                              textColor=MUTED),
        "theme": ParagraphStyle("H", fontName=regular, fontSize=9 * k,
                                leading=(12 * k * 0.98 if compact else 12),
                                textColor=MUTED, leftIndent=11),
        "_compact": compact,
        "_scale": k,
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


def _weekend_block(rows, meta, lang, st_, width, section_titles, role_labels, words):
    """The weekend sheet: talk, theme, Watchtower study, prayers."""
    data, style = [], [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
    ]
    colour = SECTION_COLORS.get("Weekend", "#8A94A0")
    widths = [width * 0.46, width * 0.18, width * 0.36]

    def row(part, label, name, guest=False):
        left = Paragraph(f'<font color="{colour}">\u25cf</font> ' + xml_escape(part),
                         st_["part"]) if part else ""
        if guest and name:
            name = f"{name}  ({words['guest_speaker']})"
        data.append([
            left,
            Paragraph(xml_escape(label), st_["label"]) if label else "",
            Paragraph(xml_escape(name), st_["name"]) if name else ""])

    def note(text):
        data.append([Paragraph("<i>" + xml_escape(text) + "</i>", st_["theme"]), "", ""])
        i = len(data) - 1
        style.extend([("SPAN", (0, i), (-1, i)),
                      ("LINEBELOW", (0, i), (-1, i), 0, colors.white)])

    def closing(r):
        return r.role == "Prayer" and clean_value(r.part_name).lower().startswith("closing")

    def rank(r):
        if r.role == "Weekend Chairman":
            return 0
        if r.role == "Prayer":
            return 9 if closing(r) else 1      # the closing prayer ends the sheet
        return {"Public Talk": 2, "Watchtower Conductor": 4,
                "Watchtower Reader": 5}.get(r.role, 3)

    def printed_title(r):
        """The left column names the part in the chosen language; the stored
        part name is English and would leak onto the Ga sheet."""
        if r.role == "Weekend Chairman":
            return words["chairman"]
        if r.role == "Prayer":
            return words["closing_prayer" if closing(r) else "opening_prayer"]
        if r.role == "Public Talk":
            return words["public_talk"]
        if r.role == "Watchtower Conductor":
            return words["watchtower"]
        if r.role == "Watchtower Reader":
            return ""                          # sits under the study, labelled
        return clean_value(r.part_name)

    listed = sorted(rows.itertuples(),
                    key=lambda r: (rank(r), int(r.sort_order or 0)))
    for r in listed:
        # the study names its conductor and reader beside the names, the way
        # the midweek sheet does for the Bible study
        label = (role_labels.get(r.role, "")
                 if r.role in ("Watchtower Conductor", "Watchtower Reader") else "")
        # only the talk is marked as a guest speaker's: a prayer said by a
        # visitor is just their name
        row(printed_title(r), label, _people(r.person, r.assistant),
            guest=(r.role == "Public Talk"
                   and bool(clean_value(getattr(r, "visitor", "")))))
        if r.role == "Public Talk":
            theme = clean_value(meta.get("talk_title"))
            number = clean_value(meta.get("talk_number"))
            if theme or number:
                bits = f"No. {number}" if number else ""
                note(f"{words['theme']}: " + " — ".join(b for b in (bits, theme) if b))

    table = Table(data, colWidths=widths)
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
    """A printable sheet per meeting: the midweek running order, or the
    weekend programme. lang is a TRANSLATIONS entry; None means English.
    compact tightens the midweek sheet so two weeks fit on one A4."""
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
        rows = schedules_df[(schedules_df["meeting_date"] == meeting_date)
                            & (schedules_df["meeting_type"] == meeting_type)]
        return bool((rows["hall"] != MAIN_HALL).any())

    def sheets(items):
        """Meetings grouped into printed sheets.

        Without compact, one per sheet as before. With it, ordinary midweek
        weeks pair up and a classroom week takes a sheet of its own — at full
        size either way, because shrinking one to fit costs more than the page.
        """
        if not compact:
            # Weekend weeks are short, so they flow and four share one A4.
            # Midweek weeks get a sheet each unless two-up is asked for: that
            # is what the checkbox is choosing between.
            out, current = [], []
            for m in items:
                if m[1] == MIDWEEK:
                    if current:
                        out.append(current)
                        current = []
                    out.append([m])
                else:
                    current.append(m)
            if current:
                out.append(current)
            return out
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
            rows = schedules_df[(schedules_df["meeting_date"] == meeting_date)
                                & (schedules_df["meeting_type"] == meeting_type)]
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
            if midweek:
                block.append(_midweek_block(rows, meta, lang, st_, width,
                                            section_titles, hall_names, role_labels,
                                            words))
            else:
                block.append(_weekend_block(rows, meta, lang, st_, width,
                                            section_titles, role_labels, words))
            block.append(Spacer(1, 10 if compact else 18))
            story.append(KeepTogether(block))

    # two versions of a week look identical on a noticeboard otherwise
    story.append(Paragraph(
        xml_escape(f"Prepared {fmt_date(date.today().isoformat())}"),
        ParagraphStyle("Made", fontName=regular, fontSize=7, leading=9,
                       textColor=MUTED, alignment=TA_RIGHT)))
    doc.build(story)
    return buffer.getvalue()


def build_s140_data(meetings, schedules_df, congregation, group_label):
    """Shape saved midweek meetings like the S-140 filler's data.json."""
    weeks, skipped = [], []
    for meeting_date, meeting_type in sorted(meetings):
        rows = schedules_df[(schedules_df["meeting_date"] == meeting_date)
                            & (schedules_df["meeting_type"] == meeting_type)]
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
    data = {"congregation": congregation, "group_label": group_label, "weeks": weeks,
            "aux": any_aux}
    if any_aux:
        # keep the Asa 2 caption and its column width for the auxiliary classroom
        data["clear_asa2"] = False
        data["asa2_shift"] = 0
    return data, skipped


# =============================================================================
# SPEAKER REMINDERS, GUEST LETTERS, ANNUAL TALK CHECKLIST
# (View Schedules, both roles — see view.py)
# =============================================================================
def upcoming_talk_reminders(schedules_df, min_days=7):
    """Public Talk speakers whose meeting is at least `min_days` away.

    Each entry: meeting_date, person (display name), talk_number, talk_title,
    is_guest (True when the name was typed in for that meeting rather than
    picked from the participants list — the `visitor` column is filled).
    """
    today = date.today()
    talk_rows = schedules_df[(schedules_df["role"] == "Public Talk")
                             & schedules_df["person"].notna()]
    out = []
    for r in talk_rows.itertuples():
        try:
            meeting = datetime.strptime(str(r.meeting_date), "%Y-%m-%d").date()
        except ValueError:
            continue
        if (meeting - today).days < min_days:
            continue
        meta = get_meeting_meta(r.meeting_date, WEEKEND)
        out.append({
            "meeting_date": r.meeting_date,
            "person": r.person,
            "talk_number": clean_value(meta.get("talk_number")),
            "talk_title": clean_value(meta.get("talk_title")),
            "is_guest": bool(clean_value(getattr(r, "visitor", ""))),
        })
    return sorted(out, key=lambda c: c["meeting_date"])


def whatsapp_reminder_text(candidate):
    """The reminder text, exactly as agreed — copy-paste only, nothing sent
    on the app's behalf."""
    return (f'Hello Brother {candidate["person"]}! This is a reminder that '
           f'you have the Public Talk "{candidate.get("talk_title") or ""}" '
           f'(No. {candidate.get("talk_number") or ""}) on '
           f'{fmt_date(candidate["meeting_date"])}.')


def _letter_date(iso):
    """'September 26, 2026' — the letter's own convention, distinct from the
    app's day-first fmt_date() used everywhere else."""
    try:
        d = datetime.strptime(str(iso), "%Y-%m-%d").date()
    except ValueError:
        return str(iso)
    return f"{d:%B} {d.day}, {d.year}"


def invitation_letter_pdf(candidate, congregation, hall_address, meeting_time,
                          signoff, phone="", email=""):
    """A formal request letter to a guest speaker's own congregation, asking
    them to release him for the visit — addressed to his congregation, not to
    him, matching the wording congregations exchange these requests in."""
    regular, bold, _ = register_fonts()
    person = candidate.get("person") or ""
    guest_congregation = candidate.get("congregation") or ""
    title = candidate.get("talk_title") or ""
    number = candidate.get("talk_number") or ""
    theme = f"No. {number} {title}".strip() if number else title

    def esc(value):
        return xml_escape(str(value or ""))

    name_style = ParagraphStyle("inv_name", fontName=bold, fontSize=18, leading=22,
                                alignment=TA_CENTER, textColor=ACCENT)
    org_style = ParagraphStyle("inv_org", fontName=bold, fontSize=13, leading=17,
                               alignment=TA_CENTER)
    addr_style = ParagraphStyle("inv_addr", fontName=regular, fontSize=8.5,
                                leading=11, alignment=TA_CENTER, textColor=MUTED)
    body_style = ParagraphStyle("inv_body", fontName=regular, fontSize=10.5,
                                leading=16)
    heading_style = ParagraphStyle("inv_heading", fontName=bold, fontSize=11,
                                   leading=15, alignment=TA_CENTER)
    sign_style = ParagraphStyle("inv_sign", fontName=regular, fontSize=10.5,
                                leading=15)

    contact = f"Talk Coordinator - {esc(signoff)}"
    if phone:
        contact += f"  {esc(phone)}"
    if email:
        contact += f", {esc(email)}"

    story = [
        Paragraph(esc(congregation).upper(), name_style),
        Paragraph("CONGREGATION OF JEHOVAH’S WITNESSES", org_style),
    ]
    if hall_address:
        story.append(Paragraph(esc(hall_address), addr_style))
    story += [
        Spacer(1, 22),
        Paragraph(esc(_letter_date(date.today().isoformat())), body_style),
        Spacer(1, 20),
        Paragraph(esc(guest_congregation), body_style),
        Spacer(1, 16),
        Paragraph("Dear Brothers,", body_style),
        Spacer(1, 6),
        Paragraph("<u>REQUEST FOR PUBLIC SPEAKER</u>", heading_style),
        Spacer(1, 10),
        Paragraph("We are writing to request that the brother mentioned below "
                  "visit our congregation to give a public talk.", body_style),
        Spacer(1, 12),
        Paragraph(f"Name: {esc(person)}<br/>"
                 f"Theme: {esc(theme)}<br/>"
                 f"Date: {esc(_letter_date(candidate['meeting_date']))}<br/>"
                 f"Time: {esc(meeting_time)}", body_style),
        Spacer(1, 12),
        Paragraph("We are hopeful that you will take into account and approve "
                  "our request. If you need more information or clarification, "
                  f"please feel free to call or send an email.<br/>{contact}",
                  body_style),
        Spacer(1, 12),
        Paragraph("Please accept a warm expression of our Christian love.",
                  body_style),
        Spacer(1, 50),
        Paragraph(f"<i>Your Brothers,</i><br/>"
                 f"{esc(congregation)} Congregation of Jehovah's Witnesses",
                 sign_style),
        Spacer(1, 10),
        HRFlowable(width="50%", thickness=1, color=ACCENT, hAlign="LEFT"),
        Spacer(1, 4),
        Paragraph(f"Talk Coordinator - {esc(signoff)}", sign_style),
    ]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=54, leftMargin=54,
                            topMargin=60, bottomMargin=54)
    doc.build(story)
    return buffer.getvalue()


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
    for r in talk_rows.itertuples():
        key = (r.meeting_date, r.meeting_type)
        if key in seen_meetings:            # one Public Talk per weekend meeting
            continue
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
            given.setdefault(number, {}).setdefault(year, []).append(
                (r.meeting_date, r.person))

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


