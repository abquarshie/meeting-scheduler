# -*- coding: utf-8 -*-
"""Assignment cards as images, for sharing on WhatsApp.

Two cards, one look: the week (every part in both meetings) and one
person's month. Each is built in two steps:

    spec = week_card_spec(...)   # plain data: what the card says
    png  = render_card(spec)     # Pillow: how it looks

so the wording can be tested without pixels, and a rendered card can be
cached on its spec. Drawn at twice the layout size, so text stays sharp
after WhatsApp recompresses the image. Layout sizes below are in points
(the 1x size); S() scales them.
"""
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from constants import (
    APP_DIR,
    EN_WORDS,
    GA_WORDS,
    MAIN_HALL,
    MIDWEEK,
    ROLE_LABELS_GA,
    TRANSLATIONS,
)
from db import event_label, get_meeting_meta, get_setting, talk_text
from parts import TALK_AND_PRAYER
from sheets_pdf import SECTION_TITLES_BY_LANG, _part_title, clean_value
from utils import fmt_date, month_label, week_start

SCALE = 2
WIDTH = 720                    # points; the PNG is 1440 px wide


def S(v):
    return int(round(v * SCALE))


# -------------------------------------------------------------------- palette
INK = (23, 33, 43)
MUTED = (104, 114, 126)
FAINT = (150, 158, 168)
PAPER = (242, 240, 235)
CARD = (255, 255, 255)
RULE = (232, 234, 238)
HEAD_TOP = (22, 52, 82)        # header gradient, from the app's ink blue
HEAD_BOTTOM = (36, 82, 122)
ACCENT = (36, 82, 122)
SECTION = {                    # the workbook's own section colours
    "Opening": (138, 148, 160), "Treasures": (91, 103, 112),
    "Ministry": (183, 130, 31), "Living": (142, 42, 42),
    "Closing": (138, 148, 160), "Weekend": (31, 78, 95),
}
ROOM = SECTION["Ministry"]


def tint(rgb, amount):
    """The colour mixed toward white: 0 = itself, 1 = white."""
    return tuple(int(c + (255 - c) * amount) for c in rgb)


# ----------------------------------------------------------------------- type
# Inter, with DejaVu (already in the app for the PDFs) if Inter is missing.
# Both carry ɛ ɔ ŋ and the tone marks.
FONT_FILES = {"regular": "Inter-Regular.ttf", "medium": "Inter-Medium.ttf",
              "semibold": "Inter-SemiBold.ttf", "bold": "Inter-Bold.ttf",
              "display": "InterDisplay-Bold.ttf"}
FALLBACK = {"regular": "DejaVuSans.ttf", "medium": "DejaVuSans.ttf",
            "semibold": "DejaVuSans-Bold.ttf", "bold": "DejaVuSans-Bold.ttf",
            "display": "DejaVuSans-Bold.ttf"}
_fonts = {}


def font(weight, size):
    key = (weight, size)
    if key not in _fonts:
        path = Path(APP_DIR) / FONT_FILES[weight]
        if not path.is_file():
            path = Path(APP_DIR) / FALLBACK[weight]
        try:
            _fonts[key] = ImageFont.truetype(str(path), S(size))
        except OSError:                                  # pragma: no cover
            _fonts[key] = ImageFont.load_default(S(size))
    return _fonts[key]


def wrap(text, fnt, width):
    """Lines no wider than width (pixels); a single long word stays whole."""
    lines, line = [], ""
    for w in (text or "").split():
        trial = f"{line} {w}".strip()
        if fnt.getlength(trial) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines or [""]


def line_h(fnt, factor=1.32):
    return int(fnt.size * factor)


def fit(text, weight, size, width, smallest):
    """The largest size from size down to smallest at which text fits."""
    while size > smallest and font(weight, size).getlength(text) > width:
        size -= 1
    return font(weight, size)


# -------------------------------------------------------------- the wording
# Card wording that has no Ga in the app yet stays English in both: only
# wording already used on the printed sheets is given in Ga.
CARD_TEXT = {
    "title": "Meeting Assignments",
    "footer": "Can’t take your part? Tell us early.",
    "footer_one": "Can’t take one? Tell us early.",
    "prepared": "Prepared",
    "reader": "Reader",
    "guest": "Guest",
    "yours": "Your meeting assignments",
    "no_meetings": "No meetings are scheduled that week.",
    "hello": "Hello",
}
ROOM_SHORT_EN = {"aux_1": "Aux 1", "aux_2": "Aux 2"}


def _words(language):
    return GA_WORDS if language == "Ga" else EN_WORDS


def _room(hall, language):
    if not hall or hall == MAIN_HALL:
        return ""
    if language == "Ga":
        return TRANSLATIONS["Ga"].get(hall, hall)
    return ROOM_SHORT_EN.get(hall, hall)


def _plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def _role_label(r, language):
    """What an unnumbered part is called on the card."""
    words = _words(language)
    if r.role == "Public Talk":
        if language == "Ga":
            return f"{words['public_talk']} & {words['closing_prayer']}"
        return TALK_AND_PRAYER
    if language == "Ga":
        if r.role == "Watchtower Reader":
            return f"{words['watchtower']} · {words['reader']}"
        if r.role in ROLE_LABELS_GA and r.role != "Reader":
            return ROLE_LABELS_GA[r.role]
    return _part_title(r)


def _who(person, assistant):
    person, assistant = clean_value(person), clean_value(assistant)
    if person and assistant:
        return f"{person} & {assistant}"
    return person


def _prepared():
    return f"{CARD_TEXT['prepared']} {fmt_date(date.today().isoformat(), short=True)} " \
           f"{date.today().year}"


def _week_heading(monday):
    sunday = monday + timedelta(days=6)
    number = (monday.day - 1) // 7 + 1
    span = (f"{monday.day}–{sunday.day} {sunday:%b %Y}" if monday.month == sunday.month
            else f"{monday.day} {monday:%b} – {sunday.day} {sunday:%b %Y}")
    return f"Week {number} of {monday:%B} · {span}"


# ---------------------------------------------------------------- the specs
def week_card_spec(schedules_df, week_of, language="English"):
    """Everything the week's card says, as plain data."""
    monday = week_start(week_of)
    lang = TRANSLATIONS.get(language, TRANSLATIONS["English"])
    titles = SECTION_TITLES_BY_LANG.get(language, SECTION_TITLES_BY_LANG["English"])
    words = _words(language)
    spec = {"kind": "week", "congregation": get_setting("congregation", ""),
            "title": CARD_TEXT["title"], "subtitle": _week_heading(monday),
            "chip": "", "meetings": [], "empty": "",
            "footer": [CARD_TEXT["footer"], _prepared()]}

    special = event_label(monday, language)
    if special:                  # an assembly or convention week: its label only
        spec["meetings"].append({
            "eyebrow": _week_heading(monday).split(" · ")[1].upper(),
            "title": special, "detail": "", "sections": []})
        return spec

    dates = schedules_df["meeting_date"].astype(str)
    rows = schedules_df[(dates >= monday.isoformat())
                        & (dates <= (monday + timedelta(days=6)).isoformat())]
    rows = rows.sort_values(["meeting_date", "meeting_type", "sort_order"])
    parts = 0
    for (meeting_date, meeting_type), meeting in rows.groupby(
            ["meeting_date", "meeting_type"], sort=False):
        meeting_date = str(meeting_date)
        day = datetime.strptime(meeting_date, "%Y-%m-%d").date()
        meta = get_meeting_meta(meeting_date, meeting_type)
        midweek = meeting_type == MIDWEEK
        if midweek:
            detail = " · ".join(b for b in (
                clean_value(meta.get("book")) or clean_value(meta.get("heading")),
                _song(meta.get("opening_song"), words)) if b)
        else:
            talk = talk_text(meta)
            detail = f"{words['public_talk']} {talk}" if talk else ""
        sections = []
        speakers_done = False
        for r in meeting.itertuples():
            key = r.section or ("Living" if midweek else "Weekend")
            if midweek and key == "Closing":      # the closing prayer ends Living
                key = "Living"
            if not midweek:
                key = "Weekend"
            if not sections or sections[-1]["key"] != key:
                sections.append({"key": key,
                                 "title": titles.get(key, key) if midweek else "",
                                 "rows": []})
            sec = sections[-1]
            if r.role == "Public Talk":
                if speakers_done:                 # a symposium shares one line
                    continue
                speakers_done = True
                talk_rows = meeting[meeting["role"] == "Public Talk"]
                who = " & ".join(clean_value(p) for p in talk_rows["person"]
                                 if clean_value(p))
                guest = [clean_value(c) for v, c in zip(
                    talk_rows.get("visitor", []), talk_rows.get("visitor_congregation", []))
                    if clean_value(v)]
                note = ""
                if guest:
                    label = words["guest_speaker"] if language == "Ga" else CARD_TEXT["guest"]
                    note = " · ".join(b for b in (label, guest[0]) if b)
                sec["rows"].append({"part": _role_label(r, language), "who": who,
                                    "room": "", "note": note})
                parts += 1
                continue
            if r.role == "Reader" and sec["rows"] and clean_value(r.person):
                # the study's reader sits under its conductor
                label = words["reader"] if language == "Ga" else CARD_TEXT["reader"]
                prev = sec["rows"][-1]
                prev["note"] = f"{label}: {clean_value(r.person)}"
                parts += 1
                continue
            room = _room(r.hall if isinstance(r.hall, str) else MAIN_HALL, language)
            if r.role == "Aux Classroom Counselor":
                room = _room("aux_1", language)
            numbered = r.part_no == r.part_no and r.part_no is not None   # not NaN
            sec["rows"].append({
                "part": _part_title(r) if numbered else _role_label(r, language),
                "who": _who(r.person, r.assistant if r.needs_assistant == 1 else None),
                "room": room, "note": ""})
            parts += 1
        spec["meetings"].append({
            "eyebrow": f"{day:%A} · {day.day} {day:%B}".upper(),
            "title": lang["midweek_meeting" if midweek else "weekend_meeting"],
            "detail": detail, "sections": sections})
    if not spec["meetings"]:
        spec["empty"] = CARD_TEXT["no_meetings"]
    else:
        spec["chip"] = (f"{_plural(len(spec['meetings']), 'meeting')} · "
                        f"{_plural(parts, 'part')}")
    return spec


def _song(value, words):
    text = clean_value(value)
    digits = "".join(c for c in text if c.isdigit())
    return f"{words['song']} {digits}" if digits else text


def person_card_spec(name, gender, month, items, language="English"):
    """One person's month as plain data. items: month_assignments_for()."""
    lang = TRANSLATIONS.get(language, TRANSLATIONS["English"])
    title = "Sister" if gender == "Sister" else "Brother"
    tiles = []
    for it in items:
        day = datetime.strptime(it["meeting_date"], "%Y-%m-%d").date()
        midweek = it["meeting_type"] == MIDWEEK
        if it["as_assistant"]:
            sub = f"assisting {it['partner']}" if it["partner"] else "as assistant"
        elif it["partner"]:
            sub = f"with {it['partner']} assisting"
        else:
            sub = ""
        if it.get("talk"):
            sub = it["talk"]
        if it.get("shared_with"):
            sub = " · ".join(b for b in (sub, "shared with "
                                         + " and ".join(it["shared_with"])) if b)
        tiles.append({
            "day": str(day.day), "month": f"{day:%b}".upper(),
            "eyebrow": f"{day:%A} · "
                       f"{lang['midweek_meeting' if midweek else 'weekend_meeting']}".upper(),
            "part": it["part"], "sub": sub,
            "section": it.get("section") or ("Ministry" if midweek else "Weekend"),
            "room": _room(it.get("hall"), language)})
    return {"kind": "person", "congregation": get_setting("congregation", ""),
            "title": f"{CARD_TEXT['hello']}, {title} {name}",
            "subtitle": f"{CARD_TEXT['yours']} · {month_label(month)}",
            "chip": _plural(len(tiles), "assignment"), "tiles": tiles,
            "footer": [CARD_TEXT["footer_one"] if len(tiles) != 1
                       else CARD_TEXT["footer"], _prepared()]}


# ------------------------------------------------------------------ drawing
PAD = 32                       # page margin
CARD_PAD = 26
RADIUS = 22
HEADER = 196


def _shadowed_card(base, box):
    x0, y0, x1, y1 = box
    m = S(40)                                  # room for the blur to spread
    shadow = Image.new("RGBA", (x1 - x0 + 2 * m, y1 - y0 + 2 * m), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (m, m + S(6), m + x1 - x0, m + y1 - y0 + S(6)), radius=S(RADIUS),
        fill=(16, 32, 48, 34))
    shadow = shadow.filter(ImageFilter.GaussianBlur(S(12)))
    base.paste(shadow, (x0 - m, y0 - m), shadow)
    ImageDraw.Draw(base).rounded_rectangle(box, radius=S(RADIUS), fill=CARD)


def _pill(draw, x, y, text, fg, bg, size=11, weight="semibold"):
    """A rounded label with its top-left at (x, y); returns its width."""
    f = font(weight, size)
    w = f.getlength(text) + S(16)
    h = S(size + 10)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=bg)
    draw.text((x + S(8), y + h / 2), text, font=f, fill=fg, anchor="lm")
    return w


def _header(img, spec):
    h = S(HEADER)
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        grad.putpixel((0, y), tuple(int(a + (b - a) * t)
                                    for a, b in zip(HEAD_TOP, HEAD_BOTTOM)))
    img.paste(grad.resize((img.width, h)), (0, 0))
    glow = Image.new("RGBA", (img.width, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((img.width - S(260), -S(140), img.width + S(120),
                                  S(240)), fill=(255, 255, 255, 22))
    glow = glow.filter(ImageFilter.GaussianBlur(S(2)))
    img.paste(glow, (0, 0), glow)
    draw = ImageDraw.Draw(img, "RGBA")
    x, room = S(PAD), img.width - 2 * S(PAD)
    if spec.get("congregation"):
        draw.text((x, S(40)), spec["congregation"].upper(),
                  font=fit(spec["congregation"].upper(), "semibold", 12, room, 9),
                  fill=(255, 255, 255, 170))
    draw.text((x, S(62)), spec["title"],
              font=fit(spec["title"], "display", 34, room, 22), fill=(255, 255, 255))
    draw.text((x, S(112)), spec["subtitle"],
              font=fit(spec["subtitle"], "medium", 16, room, 12),
              fill=(255, 255, 255, 200))
    if spec.get("chip"):
        _pill(draw, x, S(146), spec["chip"], (255, 255, 255), (255, 255, 255, 40), 12)


def _footer(img, y, left, right):
    draw = ImageDraw.Draw(img, "RGBA")
    f = font("medium", 12)
    draw.text((S(PAD), y), left, font=f, fill=MUTED)
    draw.text((img.width - S(PAD), y), right, font=f, fill=FAINT, anchor="ra")


def _png(img):
    out = BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


# ---- the week card
def _row_layout(row, part_w, who_w):
    pf, wf, nf = font("regular", 14), font("semibold", 14), font("regular", 12)
    part_lines = wrap(row["part"], pf, part_w)
    tag = font("semibold", 10).getlength(row["room"]) + S(24) if row["room"] else 0
    room = who_w - tag
    who = row["who"] or "—"
    if " & " in who and wf.getlength(who) > room:
        # a pair breaks at the "&", never inside a name
        first, second = who.split(" & ", 1)
        who_lines = wrap(first + " &", wf, room) + wrap(second, wf, room)
    else:
        who_lines = wrap(who, wf, room)
    note_lines = wrap(row["note"], nf, who_w) if row["note"] else []
    h = max(len(part_lines) * line_h(pf),
            len(who_lines) * line_h(wf) + len(note_lines) * line_h(nf))
    return part_lines, who_lines, note_lines, h + S(14)


def _meeting_height(m, inner):
    h = S(CARD_PAD) + S(18) + S(34) + (S(22) if m["detail"] else 0) + S(8)
    part_w, who_w = inner * 0.56, inner * 0.40
    for sec in m["sections"]:
        h += S(36) if sec["title"] else S(6)
        for r in sec["rows"]:
            h += _row_layout(r, part_w, who_w)[3]
    return h + S(CARD_PAD)


def _draw_meeting(img, m, top):
    x0, x1 = S(PAD), img.width - S(PAD)
    inner = (x1 - x0) - 2 * S(CARD_PAD)
    bottom = top + _meeting_height(m, inner)
    _shadowed_card(img, (x0, top, x1, bottom))
    draw = ImageDraw.Draw(img, "RGBA")
    x, right = x0 + S(CARD_PAD), x1 - S(CARD_PAD)
    y = top + S(CARD_PAD)
    draw.text((x, y), m["eyebrow"], font=font("bold", 12), fill=ACCENT)
    y += S(18)
    draw.text((x, y), m["title"], font=fit(m["title"], "display", 24, inner, 16),
              fill=INK)
    y += S(34)
    if m["detail"]:
        draw.text((x, y), wrap(m["detail"], font("medium", 13), inner)[0],
                  font=font("medium", 13), fill=MUTED)
        y += S(22)
    y += S(8)
    part_w, who_w = inner * 0.56, inner * 0.40
    pf, wf, nf = font("regular", 14), font("semibold", 14), font("regular", 12)
    for sec in m["sections"]:
        colour = SECTION.get(sec["key"], MUTED)
        if sec["title"]:
            draw.rounded_rectangle((x, y + S(6), x + S(4), y + S(22)), radius=S(2),
                                   fill=colour)
            draw.text((x + S(12), y + S(14)), sec["title"].upper(),
                      font=font("bold", 11), fill=colour, anchor="lm")
            y += S(36)
        else:
            y += S(6)
        for i, r in enumerate(sec["rows"]):
            part_lines, who_lines, note_lines, h = _row_layout(r, part_w, who_w)
            ty = y
            for ln in part_lines:
                draw.text((x, ty), ln, font=pf, fill=MUTED)
                ty += line_h(pf)
            if r["room"]:                  # the room, just left of the name
                tw = font("semibold", 10).getlength(r["room"]) + S(16)
                nx = right - wf.getlength(who_lines[0]) - S(8) - tw
                _pill(draw, nx, y + S(1), r["room"], ROOM, tint(ROOM, 0.86), 10)
            ty = y
            for ln in who_lines:
                draw.text((right, ty), ln, font=wf,
                          fill=INK if r["who"] else FAINT, anchor="ra")
                ty += line_h(wf)
            for ln in note_lines:
                draw.text((right, ty), ln, font=nf, fill=MUTED, anchor="ra")
                ty += line_h(nf)
            y += h
            if i < len(sec["rows"]) - 1:
                draw.line((x, y - S(7), right, y - S(7)), fill=RULE, width=S(0.75))
    return bottom


def _render_week(spec):
    inner = S(WIDTH) - 2 * S(PAD) - 2 * S(CARD_PAD)
    body = sum(_meeting_height(m, inner) + S(22) for m in spec["meetings"])
    if spec["empty"]:
        body = S(110)
    height = S(HEADER) + S(26) + body + S(60)
    img = Image.new("RGB", (S(WIDTH), height), PAPER)
    _header(img, spec)
    y = S(HEADER) + S(26)
    if spec["empty"]:
        _shadowed_card(img, (S(PAD), y, img.width - S(PAD), y + S(88)))
        ImageDraw.Draw(img).text((img.width / 2, y + S(44)), spec["empty"],
                                 font=font("medium", 15), fill=MUTED, anchor="mm")
        y += S(110)
    for m in spec["meetings"]:
        y = _draw_meeting(img, m, y) + S(22)
    _footer(img, y + S(6), *spec["footer"])
    return _png(img)


# ---- the person card
def _tile_layout(t, text_w):
    pf = font("semibold", 17)
    part_lines = wrap(t["part"], pf, text_w)[:2]
    sub_lines = wrap(t["sub"], font("regular", 13), text_w)[:2] if t["sub"] else []
    body = S(22) + S(18) + len(part_lines) * line_h(pf) \
        + (S(6) + len(sub_lines) * line_h(font("regular", 13)) if sub_lines else 0)
    return part_lines, sub_lines, max(S(104), body + S(22))


def _render_person(spec):
    x0, x1 = S(PAD), S(WIDTH) - S(PAD)
    tx_off = S(18) + S(68) + S(18)
    text_w = (x1 - x0) - tx_off - S(24) - S(70)       # room for a room tag
    layouts = [_tile_layout(t, text_w) for t in spec["tiles"]]
    height = S(HEADER) + S(26) + sum(h + S(16) for *_, h in layouts) + S(76)
    img = Image.new("RGB", (S(WIDTH), height), PAPER)
    _header(img, spec)
    y = S(HEADER) + S(26)
    for t, (part_lines, sub_lines, tile_h) in zip(spec["tiles"], layouts):
        _shadowed_card(img, (x0, y, x1, y + tile_h))
        draw = ImageDraw.Draw(img, "RGBA")
        colour = SECTION.get(t["section"], ACCENT)
        bx, mid = x0 + S(18), y + tile_h / 2
        draw.rounded_rectangle((bx, mid - S(34), bx + S(68), mid + S(34)),
                               radius=S(14), fill=tint(colour, 0.88))
        draw.text((bx + S(34), mid - S(15)), t["month"], font=font("bold", 11),
                  fill=colour, anchor="mm")
        draw.text((bx + S(34), mid + S(11)), t["day"], font=font("display", 26),
                  fill=colour, anchor="mm")
        tx, ty = x0 + tx_off, y + S(22)
        draw.text((tx, ty), t["eyebrow"],
                  font=fit(t["eyebrow"], "bold", 11, text_w, 8), fill=MUTED)
        ty += S(18)
        pf = font("semibold", 17)
        for ln in part_lines:
            draw.text((tx, ty), ln, font=pf, fill=INK)
            ty += line_h(pf)
        if sub_lines:
            ty += S(6)
            for ln in sub_lines:
                draw.text((tx, ty), ln, font=font("regular", 13), fill=MUTED)
                ty += line_h(font("regular", 13))
        if t["room"]:
            w = font("semibold", 10).getlength(t["room"]) + S(16)
            _pill(draw, x1 - S(20) - w, y + S(20), t["room"], ROOM, tint(ROOM, 0.86), 10)
        y += tile_h + S(16)
    _footer(img, y + S(10), *spec["footer"])
    return _png(img)


def render_card(spec):
    """The card as PNG bytes."""
    return (_render_week if spec["kind"] == "week" else _render_person)(spec)

