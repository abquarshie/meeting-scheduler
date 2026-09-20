# -*- coding: utf-8 -*-
"""S-89 assignment slips, printed on the official blank form.

The app does not draw its own version of the form: the blank is uploaded once
under Admin and filled here, so the printed wording is always the real thing.
"""
from pathlib import Path

from sheets_pdf import *  # noqa: F401,F403


class S89Error(Exception):
    pass


def fill_s89(template_bytes, slip_rows, lang=None):
    """The official blank S-89, filled, four slips to a page.

    The text is drawn into the form's field rectangles and the fields removed,
    rather than set as form values: the form's own font carries no ɛ ɔ ŋ, so a
    filled field would silently drop them from Ga names.
    """
    try:
        import pymupdf
    except ImportError as exc:                              # pragma: no cover
        raise S89Error("PyMuPDF is needed to fill the official form.") from exc
    regular, _, supports_ga = register_fonts()
    font_path = None
    for candidate, _bold in FONT_CANDIDATES:
        if candidate and Path(candidate).exists():
            font_path = str(candidate)
            break
    if font_path is None:
        raise S89Error("No font with ɛ, ɔ and ŋ was found for the slips.")

    try:
        template = pymupdf.open(stream=template_bytes, filetype="pdf")
        widgets = sorted(template[0].widgets(),
                         key=lambda w: int(w.field_name.split("_")[1]))
    except Exception as exc:
        # PyMuPDF raises its own error types for a damaged or non-PDF file;
        # everything here has to arrive as S89Error so printing can fall back
        raise S89Error(
            "This file couldn't be read as the fillable S-89 blank form: "
            f"{str(exc)[:120]}") from exc
    if len(widgets) < 7:
        raise S89Error(
            f"Expected the S-89's form fields; found {len(widgets)}. "
            "Upload the fillable blank form, not a scan or a printout.")
    # the rectangles come from the template: copying a page does not copy its
    # form fields, so the copies have none to read
    boxes = [w.rect for w in widgets]
    per_page = len(boxes) // 7

    out = pymupdf.open()
    rows = list(slip_rows)
    while not rows or len(rows) % per_page:
        rows.append(None)       # spare blanks fill the sheet; none at all
                                # still prints one sheet rather than no pages

    for start in range(0, len(rows), per_page):
        out.insert_pdf(template, from_page=0, to_page=0)
        page = out[-1]
        for slot, row in enumerate(rows[start:start + per_page]):
            fields = boxes[slot * 7:(slot + 1) * 7]
            if row is None or len(fields) < 7:
                continue
            part_no = row.get("part_no")
            values = [
                str(row.get("person") or ""),
                str(row.get("assistant") or ""),
                fmt_date(row["meeting_date"]) if row.get("meeting_date") else "",
                str(part_no) if part_no else str(row.get("part_name") or ""),
            ]
            for rect, value in zip(fields[:4], values):
                if value:
                    page.insert_text((rect.x0 + 2, rect.y1 - 5), value,
                                     fontname="SlipTTF", fontfile=font_path,
                                     fontsize=9)
            hall = row.get("hall") or MAIN_HALL
            if hall != hall:                    # NaN
                hall = MAIN_HALL
            index = HALLS.index(hall) if hall in HALLS else 0
            tick = fields[4 + index]
            page.insert_text((tick.x0 + 1.5, tick.y1 - 2), "X",
                             fontname="SlipTTF", fontfile=font_path, fontsize=9)
        for widget in list(page.widgets() or []):
            page.delete_widget(widget)
    return out.tobytes()


def check_s89_template(template_bytes):
    """Raise S89Error unless this looks like the fillable blank S-89.

    Used before storing an upload, so a wrong file is refused at the point it
    is chosen rather than when someone tries to print.
    """
    try:
        import pymupdf
    except ImportError as exc:                              # pragma: no cover
        raise S89Error("PyMuPDF is needed to read the official form.") from exc
    try:
        doc = pymupdf.open(stream=template_bytes, filetype="pdf")
        widgets = sorted(doc[0].widgets(),
                         key=lambda w: int(w.field_name.split("_")[1]))
    except Exception as exc:
        raise S89Error(
            "This file couldn't be read as the fillable S-89 blank form: "
            f"{str(exc)[:120]}") from exc
    if len(widgets) < 7:
        raise S89Error(
            f"Expected the S-89's form fields; found {len(widgets)}. "
            "Upload the fillable blank form, not a scan or a printout.")
    return len(widgets) // 7



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


def slips_pdf(slip_rows, lang, language_name):
    """Slips printed on the official blank S-89 for this language.

    The app used to draw its own imitation of the form as a fallback. Keeping a
    hand-typed copy of the printed wording in step with the real thing was a
    losing game, so the blank is now required — upload it once under Admin.
    """
    blank, _ = load_template(f"s89_{language_name}")
    if not blank:
        raise S89Error(
            f"No blank S-89 has been uploaded for {language_name}. "
            "Add one under Admin → Official S-89 blank.")
    return fill_s89(blank, slip_rows, lang)
