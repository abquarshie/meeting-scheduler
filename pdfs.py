# -*- coding: utf-8 -*-
"""S-89 slips, printable schedules and S-140 data."""
import io
import re
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
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


def generate_slips_pdf(slip_rows, lang):
    """slip_rows: dicts with person, assistant, part_no, part_name, meeting_date, hall."""
    regular, bold, _ = register_fonts()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18, leftMargin=18,
                            topMargin=18, bottomMargin=18)
    header_style = ParagraphStyle("SlipHeader", fontSize=8, leading=10,
                                  alignment=1, fontName=bold)
    field_style = ParagraphStyle("SlipField", fontSize=9, leading=12, fontName=regular)
    note_style = ParagraphStyle("SlipNote", fontSize=6.5, leading=8.5, fontName=regular)

    def slip(row):
        filled = row is not None
        row = row or {}

        def tick(key):
            # NaN and None both mean the main hall; NaN is truthy, so test it first
            hall = row.get("hall") or MAIN_HALL
            if hall != hall:                      # NaN
                hall = MAIN_HALL
            return "[X]" if filled and key == hall else "[&nbsp;&nbsp;]"

        name = xml_escape(row.get("person") or "")
        assistant = xml_escape(row.get("assistant") or "") or "_" * 25
        when = fmt_date(row["meeting_date"]) if row.get("meeting_date") else ""
        part_no = row.get("part_no")
        part = str(part_no) if part_no else xml_escape(row.get("part_name") or "")
        return [
            Paragraph(xml_escape(lang["slip_title"]).replace("\n", "<br/>"), header_style),
            Spacer(1, 6),
            Paragraph(f"<b>{xml_escape(lang['name'])}</b> {name}", field_style),
            Spacer(1, 3),
            Paragraph(f"<b>{xml_escape(lang['assistant'])}</b> {assistant}", field_style),
            Spacer(1, 3),
            Paragraph(
                f"<b>{xml_escape(lang['date'])}</b> {when}&nbsp;&nbsp;&nbsp;&nbsp;"
                f"<b>{xml_escape(lang['part_no'])}</b> {part}",
                field_style,
            ),
            Spacer(1, 4),
            Paragraph(f"<b>{xml_escape(lang['to_be_given'])}</b>", field_style),
            Paragraph(
                "<br/>".join(f"{tick(h)} {xml_escape(lang[h])}" for h in HALLS),
                field_style,
            ),
            Spacer(1, 4),
            Paragraph(xml_escape(lang["note"]), note_style),
            Spacer(1, 2),
            Paragraph(f"<font color='gray'>{xml_escape(lang['form_code'])}</font>", note_style),
        ]

    rows = list(slip_rows)
    while len(rows) % 4:
        rows.append(None)  # spare blank slips fill the page

    story = []
    for i in range(0, len(rows), 4):
        batch = rows[i:i + 4]
        table = Table(
            [[slip(batch[0]), slip(batch[1])], [slip(batch[2]), slip(batch[3])]],
            colWidths=[270, 270],
            rowHeights=[385, 385],
        )
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey, 1, (3, 3)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(table)
        if i + 4 < len(rows):
            story.append(PageBreak())
    doc.build(story)
    return buffer.getvalue()


def generate_schedule_pdf(meetings, schedules_df):
    """One printable block per (date, type)."""
    regular, bold, _ = register_fonts()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36,
                            topMargin=36, bottomMargin=36)
    title_style = ParagraphStyle("T", fontName=bold, fontSize=12, leading=15, spaceAfter=4)
    sub_style = ParagraphStyle("S", fontName=regular, fontSize=9, leading=11,
                               textColor=colors.grey, spaceAfter=6)
    cell_style = ParagraphStyle("C", fontName=regular, fontSize=9, leading=11)
    sec_style = ParagraphStyle("H", fontName=bold, fontSize=9, leading=11,
                               textColor=colors.white)
    story = []
    for meeting_date, meeting_type in meetings:
        rows = schedules_df[(schedules_df["meeting_date"] == meeting_date)
                            & (schedules_df["meeting_type"] == meeting_type)]
        meta = get_meeting_meta(meeting_date, meeting_type)
        block = [Paragraph(xml_escape(f"{meeting_type} — {fmt_date(meeting_date)}"), title_style)]
        if meta.get("heading"):
            block.append(Paragraph(xml_escape(meta["heading"]), sub_style))
        data, style = [], [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        current = None
        for _, r in rows.iterrows():
            section = r["section"] or ""
            if section != current:
                current = section
                data.append([Paragraph(xml_escape(SECTION_TITLES.get(section, section)),
                                       sec_style), ""])
                style += [("SPAN", (0, len(data) - 1), (1, len(data) - 1)),
                          ("BACKGROUND", (0, len(data) - 1), (1, len(data) - 1),
                           colors.HexColor("#30363d"))]
            slot = make_slot(r["part_name"], r["role"] or "", section,
                             int(r["part_no"]) if pd.notna(r["part_no"]) else None,
                             int(r["minutes"]) if pd.notna(r["minutes"]) else None,
                             r["hall"])
            who = r["person"] or "—"
            if r["assistant"]:
                who += f" / {r['assistant']}"
            data.append([Paragraph(xml_escape(slot_label(slot)), cell_style),
                         Paragraph(xml_escape(who), cell_style)])
            if r["role"] == "Public Talk" and talk_text(meta):
                data.append([Paragraph("<i>" + xml_escape(talk_text(meta)) + "</i>",
                                       cell_style), ""])
                style.append(("SPAN", (0, len(data) - 1), (1, len(data) - 1)))
        table = Table(data, colWidths=[300, 223])
        table.setStyle(TableStyle(style))
        block += [table, Spacer(1, 18)]
        story.append(KeepTogether(block))
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
        weeks.append(week)
    any_aux = any(w["aux"] for w in weeks)
    data = {"congregation": congregation, "group_label": group_label, "weeks": weeks,
            "aux": any_aux}
    if any_aux:
        # keep the Asa 2 caption and its column width for the auxiliary classroom
        data["clear_asa2"] = False
        data["asa2_shift"] = 0
    return data, skipped


def row_slot(r):
    """make_slot() from a schedules row (dict or namedtuple)."""
    get = r.get if isinstance(r, dict) else lambda k, d=None: getattr(r, k, d)
    part_no, minutes = get("part_no"), get("minutes")
    return make_slot(get("part_name"), get("role") or "", get("section"),
                     int(part_no) if pd.notna(part_no) else None,
                     int(minutes) if pd.notna(minutes) else None, get("hall"))


def reminder_rows(rows):
    """Assignments that get a reminder (everyone except the chairmen)."""
    return rows[rows["person"].notna()
                & ~rows["role"].isin(["Chairman", "Weekend Chairman"])]


def reminder_message(r, meeting_type, meeting_date, meta):
    slot = row_slot(r)
    part_txt = slot_label({**slot, "hall": MAIN_HALL})  # room named separately
    lines = [f"Hi {r.person},",
             f"You have a part at the {meeting_type.lower()} on {fmt_date(meeting_date)}."]
    if meta.get("heading"):
        lines.append(meta["heading"])
    lines.append(f"Part: {part_txt}")
    if r.role == "Public Talk" and talk_text(meta):
        lines.append(f"Talk: {talk_text(meta)}")
    if r.hall and r.hall != MAIN_HALL:
        lines.append(f"Room: {HALL_WORDS.get(r.hall, r.hall)}")
    if r.assistant and r.needs_assistant == 1:
        lines.append(f"Assistant: {r.assistant}")
    lines.append("Please let me know if you can't. Thank you!")
    return part_txt, "\n".join(lines)


def slip_rows_for(rows):
    """S-89 slip data for the student parts in these schedule rows."""
    student_rows = rows[(rows["student_part"] == 1) & rows["person"].notna()]
    student_rows = student_rows.sort_values(["meeting_date", "hall", "sort_order"])
    return [
        {"person": r.person, "assistant": r.assistant,
         "part_no": int(r.part_no) if pd.notna(r.part_no) else None,
         "part_name": r.part_name, "meeting_date": r.meeting_date, "hall": r.hall}
        for r in student_rows.itertuples()
    ]
