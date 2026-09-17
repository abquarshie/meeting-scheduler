# -*- coding: utf-8 -*-
"""Replacement for generate_schedule_pdf() in pdfs.py.

Lays the printable schedule out like the Midweek Meeting Schedule sheet:
a blue date/scripture line per week, coloured section headings, songs in
place, bold role labels beside the names, and — on auxiliary-classroom
weeks — a second name column.

No running clock: the left column carries the part and its minutes only.

Before pasting into pdfs.py, add to constants.py (and delete the duplicate
SECTION_COLORS/SECTION_NAMES from ui.py, which reaches them by star import):

    SECTION_COLORS = {
        "Treasures": "#5B6770", "Ministry": "#B7821F", "Living": "#8E2A2A",
        "Opening": "#8A94A0", "Closing": "#8A94A0", "Weekend": "#8A94A0",
    }
    ROLE_LABELS = {
        "Prayer": "Prayer",
        "Chairman": "Chairman",
        "Weekend Chairman": "Chairman",
        "Bible Study Conductor": "Conductor",
        "Reader": "Reader",
        "Watchtower Conductor": "Conductor",
        "Watchtower Reader": "Reader",
        "Aux Classroom Counselor": "Auxiliary Classroom Counselor",
    }
"""
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from xml.sax.saxutils import escape as xml_escape
import io

# --- these come from pdfs.py's own star imports; listed here so this file
# --- can be smoke-tested on its own.
try:
    from workbook import *  # noqa: F401,F403
except ImportError:  # pragma: no cover - standalone use
    pass

HEADING_BLUE = colors.HexColor("#1F6FB2")


def _part_text(part_name, minutes):
    """'Bible Reading (4 min.)' — no part number, no running time."""
    title = (part_name or "").strip()
    try:
        mins = int(float(minutes))      # pandas hands NaN over for blank minutes
    except (TypeError, ValueError):
        mins = None
    if mins and "min" not in title.lower():
        title += f" ({mins} min.)"
    return title


def _clean(value):
    """'' for None, NaN and blanks — NaN is truthy, so `or` alone isn't enough."""
    if value is None or value != value:
        return ""
    return str(value).strip()


def _people(person, assistant):
    person, assistant = _clean(person), _clean(assistant)
    if person and assistant:
        return f"{person} & {assistant}"
    return person


def generate_schedule_pdf(meetings, schedules_df):
    """One block per (date, type), laid out like the printed schedule sheet."""
    regular, bold, _ = register_fonts()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36,
                            topMargin=36, bottomMargin=36)

    banner = ParagraphStyle("Banner", fontName=bold, fontSize=15, leading=18)
    banner_right = ParagraphStyle("BannerR", parent=banner, alignment=TA_RIGHT)
    week_style = ParagraphStyle("Week", fontName=bold, fontSize=11.5, leading=14,
                                textColor=HEADING_BLUE, spaceBefore=10, spaceAfter=2)
    part_style = ParagraphStyle("Part", fontName=regular, fontSize=8.5, leading=11,
                                leftIndent=10, firstLineIndent=-10)
    name_style = ParagraphStyle("Name", fontName=regular, fontSize=8.5, leading=11)
    label_style = ParagraphStyle("Label", fontName=bold, fontSize=8, leading=11,
                                 alignment=TA_RIGHT)
    sub_style = ParagraphStyle("Sub", fontName=bold, fontSize=7, leading=9)
    talk_style = ParagraphStyle("Talk", fontName=regular, fontSize=8.5, leading=11,
                                textColor=colors.HexColor("#555555"), leftIndent=10)

    congregation = get_setting("congregation", "")
    story = []

    for meeting_date, meeting_type in meetings:
        rows = schedules_df[(schedules_df["meeting_date"] == meeting_date)
                            & (schedules_df["meeting_type"] == meeting_type)]
        meta = get_meeting_meta(meeting_date, meeting_type)
        aux_week = bool((rows["hall"] != MAIN_HALL).any())
        n_cols = 4 if aux_week else 3
        widths = [250, 100, 60, 113] if aux_week else [300, 70, 153]

        title_row = Table(
            [[Paragraph(f"{xml_escape(meeting_type)} Schedule", banner),
              Paragraph(xml_escape(congregation), banner_right)]],
            colWidths=[sum(widths) * 0.62, sum(widths) * 0.38],
            style=[("LEFTPADDING", (0, 0), (-1, -1), 0),
                   ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                   ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                   ("LINEBELOW", (0, 0), (-1, -1), 1.2, colors.black)])
        block = [title_row]

        book = meta.get("book") or meta.get("heading") or ""
        block.append(Paragraph(
            f"{xml_escape(fmt_date(meeting_date))}"
            + (f"&nbsp;&nbsp;|&nbsp;&nbsp;{xml_escape(book.upper())}" if book else ""),
            week_style))

        data, style = [], [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]

        def pad(cells):
            return list(cells) + [""] * (n_cols - len(cells))

        def add_row(part="", aux="", label="", name="", color=None,
                    wide_label=False):
            """One line: part text on the left, names on the right."""
            left = Paragraph(
                (f'<font color="{color}">\u2022</font> ' if color and part else "")
                + xml_escape(part), part_style) if part else ""
            label_cell = Paragraph(xml_escape(label), label_style) if label else ""
            cells = [left]
            if aux_week and wide_label:
                # no aux name on this row, so the label spans that column too.
                # a span shows the top-left cell, so the label must sit there.
                cells += [label_cell, ""]
                style.append(("SPAN", (1, len(data)), (2, len(data))))
            else:
                if aux_week:
                    cells.append(Paragraph(xml_escape(aux), name_style) if aux else "")
                cells.append(label_cell)
            cells.append(Paragraph(xml_escape(name), name_style) if name else "")
            data.append(pad(cells))

        def add_section(section):
            color = SECTION_COLORS.get(section, "#8A94A0")
            title = SECTION_TITLES.get(section, section or "")
            data.append(pad([Paragraph(
                f'<font color="{color}" size="9"><b>\u25a0&nbsp;&nbsp;'
                f'{xml_escape(title)}</b></font>',
                part_style)]))
            i = len(data) - 1
            style.extend([("SPAN", (0, i), (-1, i)),
                          ("TOPPADDING", (0, i), (-1, i), 9)])
            return color

        def add_song(song, label="", name=""):
            if song or name:
                add_row(song or "", label=label, name=name, wide_label=True,
                        color=SECTION_COLORS.get("Living", "#8A94A0"))

        by_section = {}
        for r in rows.itertuples():
            by_section.setdefault(r.section or "", []).append(r)

        if meeting_type == MIDWEEK:
            opening = by_section.get("Opening", [])
            closing = by_section.get("Closing", [])
            prayer_open = next((r for r in opening if r.role == "Prayer"), None)
            prayer_close = next((r for r in closing if r.role == "Prayer"), None)

            add_song(meta.get("opening_song"), "Prayer",
                     _clean(prayer_open.person) if prayer_open else "")
            for r in opening:
                if r.role == "Prayer":
                    continue
                add_row(label=ROLE_LABELS.get(r.role, ""),
                        name=_clean(r.person), wide_label=True)

            sub_done = False
            for section in ("Treasures", "Ministry", "Living"):
                members = by_section.get(section)
                if not members:
                    continue
                color = add_section(section)
                if section == "Living":
                    add_song(meta.get("middle_song"))
                main = [r for r in members if r.hall == MAIN_HALL]
                extra = {(r.role, r.part_no): r for r in members if r.hall != MAIN_HALL}
                for r in main:
                    other = extra.get((r.role, r.part_no))
                    if other is not None and not sub_done:
                        data.append(pad([
                            "", Paragraph("Auxiliary Classroom", sub_style), "",
                            Paragraph("Main Hall", sub_style)]))
                        sub_done = True
                    part = "" if r.role == "Reader" else _part_text(r.part_name, r.minutes)
                    add_row(part,
                            aux=_people(other.person, other.assistant) if other else "",
                            label=ROLE_LABELS.get(r.role, ""),
                            name=_people(r.person, r.assistant),
                            color=color)

            add_song(meta.get("closing_song"), "Prayer",
                     _clean(prayer_close.person) if prayer_close else "")
        else:
            color = add_section("Weekend")
            for r in rows.itertuples():
                add_row(_part_text(r.part_name, r.minutes),
                        label=ROLE_LABELS.get(r.role, ""),
                        name=_people(r.person, r.assistant), color=color)
                if r.role == "Public Talk" and talk_text(meta):
                    data.append(pad([Paragraph(
                        "<i>" + xml_escape(talk_text(meta)) + "</i>", talk_style)]))
                    style.append(("SPAN", (0, len(data) - 1), (-1, len(data) - 1)))

        table = Table(data, colWidths=widths)
        table.setStyle(TableStyle(style))
        block += [table, Spacer(1, 16)]
        story.append(KeepTogether(block))

    doc.build(story)
    return buffer.getvalue()
