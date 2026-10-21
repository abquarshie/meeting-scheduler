# -*- coding: utf-8 -*-
"""The Python half of the Next.js app, as one Vercel function at /api/py.

The scheduling rules (who may take a part, rotation, suggestions, the checks
before a save, undo) and every document (S-89 slips, the S-140, schedule
sheets, share cards, letters, backups) stay in the Python modules the
Streamlit app already uses and tests. This file only puts them behind HTTP:
`/api/py?op=<name>`, JSON in and out, or a file for downloads.

The browser calls it directly, carrying the sign-in cookie the Next.js app
set; it is checked here with the same SESSION_SECRET.
"""
import base64
from datetime import date, timedelta
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import sys
import time
import traceback
from urllib.parse import parse_qs, quote, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import st_shim  # noqa: E402  (must come before the app's modules)

if not os.environ.get("MEETING_DSN") and os.environ.get("DATABASE_URL"):
    os.environ["MEETING_DSN"] = os.environ["DATABASE_URL"]

import pandas as pd  # noqa: E402

from backup import backup_bytes, import_all  # noqa: E402
from card_image import person_card_spec, render_card, week_card_spec  # noqa: E402
from constants import MAIN_HALL, MIDWEEK, SISTER_ROLES, TRANSLATIONS, WEEKEND  # noqa: E402
import db  # noqa: E402
from parts import (FIRST_SPEAKER, TALK_AND_PRAYER, apply_symposium,  # noqa: E402
                   build_midweek_slots, default_midweek_parts, default_weekend_slots,
                   is_symposium)
from picking import (assignment_issues, create_week, eligible_ids,  # noqa: E402
                     ordered_options, person_label_factory, suggest_assignments)
from s140 import S140Error, check_s140_template, fill_s140  # noqa: E402
from sheets_pdf import (build_s140_data, clean_value, generate_schedule_pdf,  # noqa: E402
                        invitation_letter_pdf, month_assignments_for,
                        outgoing_speakers_letter_pdf, talk_checklist_pdf, talk_matrix_rows,
                        week_overview_text, whatsapp_month_text)
from slips import S89Error, check_s89_template, slip_rows_for, slips_pdf  # noqa: E402
from utils import (apply_aux, fmt_date, make_slot, month_label, nfc,  # noqa: E402
                   relative_week, slot_label, slot_match_key, week_label)
import workbook as wb  # noqa: E402

COOKIE = "ms_session"


class Refused(Exception):
    """A request that can't be done, with the reason to show."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# ----------------------------------------------------------------- sign-in
def signed_in_name(cookie_header):
    """The name in a valid sign-in cookie, or None. Mirrors src/lib/session.ts."""
    secret = os.environ.get("SESSION_SECRET", "")
    if not secret or not cookie_header:
        return None
    jar = SimpleCookie()
    try:
        jar.load(cookie_header)
    except Exception:
        return None
    morsel = jar.get(COOKIE)
    if not morsel or "." not in morsel.value:
        return None
    body, sig = morsel.value.rsplit(".", 1)
    want = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    if not hmac.compare_digest(want, sig):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except Exception:
        return None
    if not isinstance(payload, dict) or payload.get("e", 0) < time.time():
        return None
    return str(payload.get("n") or "")


# ----------------------------------------------------------------- helpers
def _int(value):
    if value is None or value == "":
        return None
    return int(value)


def _students():
    return db.get_students()


def _clean_slot(raw):
    """A slot as the client sent it back, rebuilt with make_slot's fields."""
    slot = make_slot(raw.get("title") or "", raw.get("role") or "", raw.get("section") or "",
                     _int(raw.get("part_no")), _int(raw.get("minutes")),
                     raw.get("hall") or MAIN_HALL)
    slot["allow_visitor"] = bool(raw.get("allow_visitor"))
    return slot


def _picks_dict(slots, picks, symposium=False):
    """{index: (person, assistant)} for the slots chosen from the list; visitor
    slots are left out, as the Streamlit page does while editing."""
    out = {}
    for i, (slot, p) in enumerate(zip(slots, picks)):
        if p.get("isVisitor") and slot.get("allow_visitor") and not (
                symposium and slot["role"] == "Public Talk"):
            continue
        out[i] = (_int(p.get("sid")), _int(p.get("aid")))
    return out


def _context(meeting_date, meeting_type, students):
    away = db.get_unavailable(meeting_date)
    outgoing = db.get_outgoing_on(meeting_date)
    suspended = db.get_suspended(students, meeting_date)
    return away, outgoing, suspended


def _other_meeting(meeting_date, meeting_type):
    other_type = WEEKEND if meeting_type == MIDWEEK else MIDWEEK
    _, other_picks, _, _ = db.load_schedule(meeting_date, other_type)
    return other_type, {p for pair in other_picks.values() for p in pair if p}


def _issues(meeting_date, meeting_type, slots, picks_dict, students):
    _, _, suspended = _context(meeting_date, meeting_type, students)
    return assignment_issues(slots, picks_dict, students, meeting_date, meeting_type,
                             suspended, _other_meeting(meeting_date, meeting_type))


def _snapshot(meeting_date, meeting_type):
    snap = db.last_snapshot(meeting_date, meeting_type)
    if not snap:
        return None
    if snap["reason"] == "before delete":
        note = "the schedule as it was before it was deleted"
    else:
        note = (f"{snap['assigned']} assignment(s) as saved at {snap['ts'][11:16]}"
                + (f" by {snap['user']}" if snap["user"] else ""))
    return {"note": note, "reason": snap["reason"]}


# ------------------------------------------------------------ the editor
def op_editor(q):
    """Everything the Create or edit page needs for one meeting."""
    meeting_date, meeting_type = q["date"], q["type"]
    if meeting_type not in (MIDWEEK, WEEKEND):
        raise Refused("Unknown meeting type.")
    students = _students()
    today = date.today().isoformat()
    when = relative_week(meeting_date, today)
    head = {"weekLabel": week_label(meeting_date),
            "relative": when if when in ("this week", "last week", "next week") else ""}
    special = db.event_label(meeting_date)
    if special:
        return {**head, "event": special, "eventGa": db.event_label(meeting_date, "Ga")}

    schedules_df = db.get_schedules()
    saved_slots, saved_picks, saved_visitors, saved_congs = db.load_schedule(
        meeting_date, meeting_type, schedules_df)
    meta = db.get_meeting_meta(meeting_date, meeting_type)
    slots = saved_slots or (build_midweek_slots(default_midweek_parts())
                            if meeting_type == MIDWEEK else default_weekend_slots())

    workbook_info = None
    if meeting_type == MIDWEEK:
        brochure, _ = wb.load_workbook()
        if brochure:
            matched = wb.week_for_date(brochure, meeting_date)
            wb_parts = brochure[matched]["parts"] if matched else []
            saved_numbered = [(s["part_no"], s["title"]) for s in saved_slots
                              if s.get("part_no") and s.get("hall", MAIN_HALL) == MAIN_HALL]
            wb_numbered = [(p["part_no"], p["title"]) for p in wb_parts]
            differs = bool(saved_slots and matched and saved_numbered != wb_numbered)
            use = q.get("useWorkbook")
            use = (not saved_slots) if use is None else bool(use)
            week = q.get("week") if use and q.get("week") in brochure else matched
            if use and week:
                slots = build_midweek_slots(brochure[week]["parts"])
                songs = brochure[week].get("songs", [])
                if not saved_slots:
                    meta = {**meta, "heading": week, "book": brochure[week].get("book", ""),
                            "opening_song": f"Song {songs[0]}" if len(songs) > 0 else "",
                            "middle_song": f"Song {songs[1]}" if len(songs) > 1 else "",
                            "closing_song": f"Song {songs[2]}" if len(songs) > 2 else ""}
            shown = brochure.get(week) if week else None
            workbook_info = {
                "weeks": [{"label": l, "dates": wb.week_dates_text(w)} for l, w in brochure.items()],
                "matched": matched, "differs": differs, "use": use, "week": week,
                "savedCount": len(saved_numbered), "workbookCount": len(wb_numbered),
                "parts": wb.parts_summary(shown["parts"]) if shown else [],
                "gaps": shown.get("gaps", []) if shown else [],
                "text": shown.get("text", "") if shown else "",
            }

    aux_default = db.get_setting("use_aux", "1") == "1"
    aux_on = False
    if meeting_type == MIDWEEK:
        if q.get("aux") is not None:
            aux_on = bool(q["aux"])
        else:
            aux_on = bool(meta.get("aux")) if meta.get("aux") is not None else aux_default
    slots = apply_aux(slots, aux_on)
    symposium = False
    if meeting_type == WEEKEND:
        symposium = bool(q["symposium"]) if q.get("symposium") is not None else is_symposium(saved_slots)
        slots = apply_symposium(slots, symposium)

    # what is saved for each slot, matched by part number/role and hall
    picks = []
    for slot in slots:
        key = slot_match_key(slot)
        sid, aid = saved_picks.get(key, (None, None))
        visitor = saved_visitors.get(key, "")
        picks.append({"sid": sid, "aid": aid, "visitor": visitor,
                      "cong": saved_congs.get(key, ""), "isVisitor": bool(visitor)})

    away, outgoing, suspended = _context(meeting_date, meeting_type, students)
    away_all = away | outgoing
    blocked = away_all | suspended
    last_dates = db.last_assignment_dates(meeting_date)
    last_details = db.last_assignment_details(meeting_date)
    next_details = db.next_assignment_details(meeting_date)
    names = dict(zip(students["id"], students["name"]))

    people = {int(r["id"]): {"name": r["name"], "gender": r["gender"], "family": r["family"],
                             "active": int(r["active"] or 0) == 1}
              for r in students.to_dict("records")}
    general = person_label_factory(students, last_dates, away, suspended=suspended,
                                   details=last_details, meeting_date=meeting_date,
                                   outgoing=outgoing, upcoming=next_details)
    options = []
    for slot, pick in zip(slots, picks):
        role_dates = db.last_role_dates(slot["role"], meeting_date)
        eligible = eligible_ids(slot["role"], students, away_all, suspended)
        ordered = ordered_options(eligible, role_dates, keep=pick["sid"])[1:]
        label = person_label_factory(students, last_dates, away, role_dates,
                                     suspended=suspended, details=last_details,
                                     meeting_date=meeting_date, role=slot["role"],
                                     outgoing=outgoing, upcoming=next_details)
        options.append({"ids": [int(p) for p in ordered],
                        "labels": {int(p): label(p) for p in ordered},
                        "eligible": [int(p) for p in eligible],
                        "mixed": slot["role"] in SISTER_ROLES and bool(slot["student_part"])})
    # assistants: anyone active and free, least recently used first; the page
    # narrows this to the student's category or family
    active_free = [int(p) for p in students[students["active"] == 1]["id"] if p not in blocked]
    assistant_order = ordered_options(active_free, last_dates)[1:]
    for pick in picks:            # a saved assistant stays offered
        if pick["aid"] is not None and pick["aid"] not in assistant_order:
            assistant_order.append(pick["aid"])
    assistant_labels = {int(p): general(p) for p in assistant_order}

    unavailable = sorted({names[p] for p in blocked if p in names}
                         | {r["name"] for r in students.to_dict("records") if r["active"] != 1})
    labels = []
    for slot in slots:
        text = slot_label(slot)
        if slot["title"] == FIRST_SPEAKER:
            text = f"{FIRST_SPEAKER} 1 · says the Closing Prayer" if symposium else TALK_AND_PRAYER
        if aux_on and slot["student_part"] and slot["hall"] == MAIN_HALL:
            text += " · Main hall"
        labels.append(text)

    issues = assignment_issues(slots, _picks_dict(slots, picks, symposium), students,
                               meeting_date, meeting_type, suspended,
                               _other_meeting(meeting_date, meeting_type))
    return {
        **head, "event": None, "saved": bool(saved_slots), "slots": slots, "slotLabels": labels,
        "picks": picks, "meta": {k: meta.get(k) for k in (
            "heading", "book", "opening_song", "middle_song", "closing_song", "aux_group",
            "talk_number", "talk_title")},
        "workbook": workbook_info, "aux": aux_on, "symposium": symposium,
        "people": people, "options": options, "assistantOrder": [int(p) for p in assistant_order],
        "assistantLabels": assistant_labels, "unavailable": unavailable,
        "snapshot": _snapshot(meeting_date, meeting_type), "issues": issues,
        "talks": [{"number": n, "title": t} for n, t in db.get_talks()],
        "activeCount": int((students["active"] == 1).sum()),
    }


def op_check(q):
    students = _students()
    slots = [_clean_slot(s) for s in q["slots"]]
    return {"issues": _issues(q["date"], q["type"], slots,
                              _picks_dict(slots, q["picks"], bool(q.get("symposium"))), students)}


def op_suggest(q):
    """Fill the empty slots; anyone already chosen stays and is reserved."""
    meeting_date = q["date"]
    students = _students()
    slots = [_clean_slot(s) for s in q["slots"]]
    taken = {i: (_int(p.get("sid")), _int(p.get("aid")))
             for i, p in enumerate(q["picks"]) if _int(p.get("sid")) is not None}
    away, outgoing, suspended = _context(meeting_date, q["type"], students)
    picks = suggest_assignments(slots, students, away | outgoing | suspended, meeting_date,
                                skip=taken)
    return {"picks": {str(i): [v[0], v[1]] for i, v in picks.items() if v is not None}}


def op_save(q):
    meeting_date, meeting_type = q["date"], q["type"]
    students = _students()
    slots = [_clean_slot(s) for s in q["slots"]]
    symposium = bool(q.get("symposium"))
    picks = {}
    for i, (slot, p) in enumerate(zip(slots, q["picks"])):
        visitor_ok = slot.get("allow_visitor") and not (symposium and slot["role"] == "Public Talk")
        if visitor_ok and p.get("isVisitor"):
            picks[i] = (None, None)
            picks[i + 10000] = db.apply_ga_substitutes(nfc(p.get("visitor") or ""))
            if slot["role"] == "Public Talk":
                picks[i + 20000] = db.apply_ga_substitutes(nfc(p.get("cong") or ""))
        else:
            picks[i] = (_int(p.get("sid")), _int(p.get("aid")) if slot["needs_assistant"] else None)
    issues = assignment_issues(slots, picks, students, meeting_date, meeting_type,
                               _context(meeting_date, meeting_type, students)[2],
                               _other_meeting(meeting_date, meeting_type))
    errors = [x["text"] for x in issues if x["level"] == "error"]
    if errors:
        raise Refused("Not saved: " + " ".join(errors))
    meta_in = q.get("meta") or {}
    meta = {k: nfc(str(meta_in.get(k) or "")) for k in (
        "heading", "book", "opening_song", "middle_song", "closing_song", "aux_group",
        "talk_number")}
    meta["talk_title"] = db.apply_ga_substitutes(nfc(str(meta_in.get("talk_title") or "")))
    meta["aux"] = bool(q.get("aux")) if meeting_type == MIDWEEK else False
    if not meta["aux"]:
        meta["aux_group"] = ""
    names = dict(zip(students["id"], students["name"]))
    try:
        db.save_schedule(meeting_date, meeting_type, slots, picks, meta, names)
    except ValueError as exc:
        raise Refused(f"Not saved: {exc} Correct that part (or the week on the Workbook "
                      "PDF page) and save again.")
    warnings = sum(1 for x in issues if x["level"] == "warning")
    return {"message": f"Saved the {meeting_type.lower()} for {fmt_date(meeting_date)}."
            + (" The checks are still worth a look." if warnings else "")}


def op_undo(q):
    restored = db.undo_last(q["date"], q["type"])
    if restored is None:
        raise Refused("There is nothing to undo for this meeting.")
    return {"message": "Last save undone."}


def op_delete(q):
    db.delete_schedule(q["date"], q["type"])
    return {"message": "Schedule deleted. Undo on this page can bring it back."}


def op_create_month(q):
    """Create and fill several workbook weeks in one go (Month overview)."""
    students = _students()
    brochure, _ = wb.load_workbook()
    made = []
    for item in q["weeks"]:
        week = brochure.get(item["label"])
        if not week:
            continue
        filled, total = create_week(item["date"], item["label"], week, students,
                                    bool(q.get("aux")), nfc(q.get("group") or ""))
        made.append(f"{fmt_date(item['date'], short=True)} ({filled}/{total})")
    if not made:
        raise Refused("Those weeks are no longer in the workbook.")
    return {"message": "Created " + ", ".join(made) + ". Open each week to check it before printing."}


# ------------------------------------------------------- assembly weeks
def op_week_preview(q):
    day = q["day"]
    return {"label": week_label(day),
            "saved": [{"date": d, "type": t, "text": f"{t.split()[0].lower()} {fmt_date(d, short=True)}"}
                      for d, t in db.meetings_in_week(day)],
            "names": {k: {"en": db.event_text(k), "ga": db.event_text(k, "Ga")}
                      for k in ("assembly", "convention")}}


def op_mark_event(q):
    cleared = db.mark_event_week(q["day"], q["kind"])
    return {"message": f"{week_label(q['day'])} marked"
            + (f"; {len(cleared)} meeting(s) cleared." if cleared else ".")}


# ------------------------------------------------------------- workbook
def op_workbook_upload(q, body):
    if not body:
        raise Refused("Choose a PDF file first.")
    name = q.get("name") or "workbook.pdf"
    skip_past = q.get("skipPast", "1") == "1"
    weeks, empty, _raw = wb.parse_brochure(body)
    if not weeks:
        raise Refused("No numbered parts with durations were found. The PDF may be scanned, "
                      "or laid out differently. Schedules will use the standard part list.")
    first, sure = wb.guess_first_monday(weeks, name)
    dated = wb.assign_dates(dict(weeks), first)
    dropped = []
    if skip_past:
        dated, dropped = wb.drop_past_weeks(dated)
    wb.save_workbook(dated, name)
    db.set_setting("skip_past_weeks", "1" if skip_past else "0")
    db.set_setting("workbook_dates_sure", "1" if sure else "0")
    broken = wb.unreadable_parts(weeks)
    guessed = wb.guessed_roles(weeks)
    return {
        "message": f"Found parts for {len(weeks)} week(s).",
        "dropped": dropped, "empty": empty,
        "broken": [{"week": l, "title": t} for l, t in broken],
        "guessed": [{"week": l, "no": n, "title": t} for l, n, t in guessed],
        "notEnglish": not any(w.get("month") in wb.ENGLISH_MONTHS for w in weeks.values()),
    }


def op_workbook_dates(q):
    stored, file_name = wb.load_workbook()
    if not stored:
        raise Refused("No workbook is stored.")
    skip_past = bool(q.get("skipPast", True))
    dated = wb.assign_dates(stored, date.fromisoformat(q["first"]))
    if skip_past:
        dated, _ = wb.drop_past_weeks(dated)
    wb.save_workbook(dated, file_name)
    db.set_setting("skip_past_weeks", "1" if skip_past else "0")
    db.set_setting("workbook_dates_sure", "1")
    return {"message": "Week dates updated."}


def op_workbook_rename(q):
    stored, file_name = wb.load_workbook()
    label = nfc(q.get("label") or "")
    if not label or q["week"] not in stored:
        raise Refused("Type the new heading.")
    if label in stored:
        raise Refused(f"There is already a week called {label}.")
    wb.save_workbook({(label if l == q["week"] else l): w for l, w in stored.items()}, file_name)
    return {"message": f"Renamed to {label}."}


def op_workbook_week(q):
    stored, file_name = wb.load_workbook()
    week = q["week"]
    if week not in stored:
        raise Refused("That week is no longer in the workbook.")
    parts = []
    for r in q["parts"]:
        if not nfc(r.get("title") or "") or not r.get("section") or not r.get("role"):
            continue
        parts.append(make_slot(r["title"], r["role"], r["section"], _int(r.get("part_no")),
                               _int(r.get("minutes"))))
    parts.sort(key=lambda p: p["part_no"] or 99)
    numbers = [p["part_no"] for p in parts if p["part_no"]]
    top = max(numbers) if numbers else 0
    stored[week]["parts"] = parts
    stored[week]["gaps"] = [n for n in range(1, top + 1) if n not in numbers]
    wb.save_workbook(stored, file_name)
    return {"message": "Saved. Use Create or edit to assign this week."}


def op_workbook_remove(q):
    wb.save_workbook({}, "")
    return {"message": "Workbook removed."}


# ------------------------------------------------------------ templates
def op_template_upload(q, body):
    kind, language = q.get("kind"), q.get("lang")
    if kind not in ("s89", "s140") or language not in TRANSLATIONS or not body:
        raise Refused("Choose a file first.")
    name = q.get("name") or f"{kind}.{'pdf' if kind == 's89' else 'docx'}"
    try:
        if kind == "s89":
            n = check_s89_template(body)
            note = f"{n} slip(s) per page"
        else:
            n = check_s140_template(body)
            note = f"{n} week block(s) in the blank"
    except (S89Error, S140Error) as exc:
        raise Refused(str(exc))
    db.save_template(f"{kind}_{language}", name, body)
    return {"message": f"Saved the {language} {'S-89' if kind == 's89' else 'S-140'}: {note}."}


# ---------------------------------------------------------- backup
def op_restore(q, body):
    try:
        data = json.loads((body or b"").decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("This isn't a Meeting Scheduler backup.")
        counts = import_all(data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise Refused(f"That file can't be restored: {exc}")
    return {"message": f"Restored {counts.get('students', 0)} participants and "
                       f"{counts.get('schedules', 0)} schedule rows."}


# ------------------------------------------------------------ documents
def _meetings_param(q):
    out = []
    for item in (q.get("meetings") or "").split(","):
        if "|" in item:
            d, t = item.split("|", 1)
            if t in (MIDWEEK, WEEKEND):
                out.append((d, t))
    return sorted(set(out))


def _lang(q):
    language = q.get("lang") if q.get("lang") in TRANSLATIONS else (
        db.get_setting("slip_language", "") if db.get_setting("slip_language", "") in TRANSLATIONS
        else list(TRANSLATIONS)[0])
    return language, TRANSLATIONS[language]


def _rows_for(meetings):
    df = db.get_schedules()
    wanted = set(meetings)
    mask = pd.Series([(d, k) in wanted for d, k in zip(df["meeting_date"], df["meeting_type"])],
                     index=df.index, dtype=bool)
    return df, df[mask]


PDF, DOCX, PNG = ("application/pdf",
                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                  "image/png")


def doc_slips(q):
    language, t = _lang(q)
    meetings = _meetings_param(q)
    _, rows = _rows_for(meetings)
    slip_rows = slip_rows_for(rows)
    if not slip_rows:
        raise Refused("No student parts are assigned, so there are no slips to print.")
    try:
        data = slips_pdf(slip_rows, t, language)
    except S89Error as exc:
        raise Refused(str(exc))
    stem = q.get("stem") or (meetings[0][0] if meetings else "slips")
    return data, PDF, f"S89_slips_{stem}_{language}.pdf"


def doc_sheet(q):
    language, t = _lang(q)
    meetings = _meetings_param(q)
    if not meetings:
        raise Refused("No meeting chosen.")
    df = db.get_schedules()
    kind = "weekend" if all(m[1] == WEEKEND for m in meetings) else "midweek"
    data = generate_schedule_pdf(meetings, df, t, compact=q.get("compact") == "1")
    return data, PDF, f"{kind}_schedule_{q.get('stem') or meetings[0][0]}.pdf"


def doc_s140(q):
    language, t = _lang(q)
    month = q.get("month") or ""
    template, _ = db.load_template(f"s140_{language}")
    if not template:
        raise Refused(f"No {language} S-140 template. Upload the blank .docx under Admin.")
    df = db.get_schedules()
    meetings = sorted(m for m in db.saved_meetings(df) if m[1] == MIDWEEK and m[0].startswith(month))
    data, skipped = build_s140_data(meetings, df, db.get_setting("congregation"))
    data["meeting_name"] = t.get("midweek_meeting", "Midweek Meeting")
    if not data["weeks"]:
        raise Refused("Nothing to fill for that month"
                      + (" (each week needs 3 Treasures parts and a Bible Study)." if skipped else "."))
    try:
        out = fill_s140(template, data)
    except (S140Error, KeyError, IndexError) as exc:
        raise Refused(f"Couldn't fill the template: {exc}")
    return out, DOCX, f"{month_label(month)}.docx"


def doc_csv(q):
    df = db.get_schedules()
    talk = [db.talk_text(db.get_meeting_meta(r.meeting_date, r.meeting_type))
            if r.role == "Public Talk" else "" for r in df.itertuples()]
    data = df.assign(talk=talk)[
        ["meeting_date", "meeting_type", "part_no", "part_name", "talk", "minutes", "section",
         "role", "hall", "person", "assistant"]].to_csv(index=False).encode("utf-8-sig")
    return data, "text/csv; charset=utf-8", "meeting_schedule.csv"


def _person(q):
    students = _students()
    row = students[students["id"] == _int(q.get("person"))]
    if row.empty:
        raise Refused("Choose a participant.")
    return row.iloc[0]


def doc_card(q):
    language, _ = _lang(q)
    df = db.get_schedules()
    if q.get("kind") == "person":
        person, month = _person(q), q.get("month") or ""
        items = month_assignments_for(df, int(person["id"]), month)
        spec = person_card_spec(person["name"], person["gender"], month, items, language)
        stem = "_".join(str(person["name"]).split()) + f"_{month}"
    else:
        week = q.get("week") or ""
        spec = week_card_spec(df, week, language)
        stem = f"assignments_{week}"
    return render_card(spec), PNG, f"{stem}.png"


def op_message_text(q):
    language, _ = _lang(q)
    df = db.get_schedules()
    if q.get("kind") == "person":
        person, month = _person(q), q.get("month") or ""
        items = month_assignments_for(df, int(person["id"]), month)
        return {"text": whatsapp_month_text(person["name"], person["gender"], month, items)}
    return {"text": week_overview_text(df, q.get("week") or "", language)}


def _letter_settings():
    return {key: db.get_setting(key, default) for key, default in (
        ("meeting_time", ""), ("hall_address", ""),
        ("talk_coordinator_signoff", "Bernard Mensah"),
        ("talk_coordinator_phone", ""), ("talk_coordinator_email", ""))}


def doc_invitation(q):
    df = db.get_schedules()
    row = df[df["id"] == _int(q.get("row"))]
    if row.empty:
        raise Refused("That guest speaker is no longer on the schedule.")
    r = row.iloc[0]
    meta = db.get_meeting_meta(r["meeting_date"], WEEKEND)
    congregation = clean_value(r["visitor_congregation"])
    s = _letter_settings()
    missing = [label for label, key in (
        ("public meeting time", "meeting_time"), ("Kingdom Hall address", "hall_address"),
        ("Talk Coordinator sign-off name", "talk_coordinator_signoff")) if not s[key]]
    if missing:
        raise Refused("Fill in the " + ", ".join(missing) + " under Letter details first.")
    if not congregation:
        raise Refused("This speaker's congregation isn't recorded yet. Fill in "
                      "\"His congregation\" next to his name on the schedule.")
    candidate = {"meeting_date": r["meeting_date"], "person": r["person"],
                 "congregation": congregation,
                 "talk_number": clean_value(meta.get("talk_number")),
                 "talk_title": clean_value(meta.get("talk_title"))}
    data = invitation_letter_pdf(candidate, db.get_setting("congregation", ""), s["hall_address"],
                                 s["meeting_time"], s["talk_coordinator_signoff"],
                                 s["talk_coordinator_phone"], s["talk_coordinator_email"])
    return data, PDF, f"invitation_{congregation.replace(' ', '_')}_{r['meeting_date']}.pdf"


def doc_outgoing_letter(q):
    students = _students()
    names = dict(zip(students["id"], students["name"]))
    titles = dict(db.get_talks())
    speakers = sorted(((names[sid], [(n, titles.get(n, "")) for n in numbers])
                       for sid, numbers in db.get_outgoing_speakers().items() if sid in names),
                      key=lambda s: s[0].lower())
    if not speakers:
        raise Refused("Approve a speaker first.")
    s = _letter_settings()
    data = outgoing_speakers_letter_pdf(db.get_setting("congregation", ""), s["hall_address"],
                                        speakers, s["talk_coordinator_signoff"],
                                        s["talk_coordinator_phone"], s["talk_coordinator_email"])
    return data, PDF, f"outgoing_speakers_{date.today().isoformat()}.pdf"


def _years(q):
    n = max(1, min(6, _int(q.get("years")) or 3))
    return list(range(date.today().year - n + 1, date.today().year + 1))


def op_checklist(q):
    years = _years(q)
    rows = talk_matrix_rows(db.get_schedules(), years)
    return {"years": years, "rows": [
        {"number": r["number"], "title": r["title"],
         "years": {str(y): "; ".join(f"{fmt_date(d, short=True)} — {who}"
                                     for d, who in (r["years"].get(y) or [])) for y in years}}
        for r in rows]}


def doc_checklist(q):
    years = _years(q)
    rows = talk_matrix_rows(db.get_schedules(), years)
    if not rows:
        raise Refused("No talks in the list yet.")
    data = talk_checklist_pdf(rows, db.get_setting("congregation", ""), years)
    return data, PDF, f"talk_checklist_{years[0]}_{years[-1]}.pdf"


def doc_backup(q):
    return backup_bytes(), "application/json", f"meeting_scheduler_backup_{date.today()}.json"


JSON_OPS = {
    "editor": op_editor, "check": op_check, "suggest": op_suggest, "save": op_save,
    "undo": op_undo, "delete": op_delete, "create_month": op_create_month,
    "week_preview": op_week_preview, "mark_event": op_mark_event,
    "workbook_dates": op_workbook_dates, "workbook_rename": op_workbook_rename,
    "workbook_week": op_workbook_week, "workbook_remove": op_workbook_remove,
    "message_text": op_message_text, "checklist": op_checklist,
}
BODY_OPS = {"workbook_upload": op_workbook_upload, "template_upload": op_template_upload,
            "restore": op_restore}
DOCS = {"slips": doc_slips, "sheet": doc_sheet, "s140": doc_s140, "csv": doc_csv,
        "card": doc_card, "invitation": doc_invitation, "outgoing_letter": doc_outgoing_letter,
        "checklist_pdf": doc_checklist, "backup": doc_backup}
# GET requests are only for reading: documents, and a few read-only JSON ops
GET_JSON = {"message_text", "checklist", "week_preview"}


def handle(method, path, headers, body):
    """(status, content type, bytes, extra headers) for one request."""
    url = urlparse(path)
    q = {k: v[-1] for k, v in parse_qs(url.query).items()}
    op = q.get("op", "")
    name = signed_in_name(headers.get("cookie") or headers.get("Cookie"))
    if name is None:
        return 401, "application/json", b'{"error": "Please sign in again."}', {}
    st_shim.new_request(name)
    try:
        if method == "GET" and op in DOCS:
            data, ctype, file_name = DOCS[op](q)
            disposition = "inline" if ctype == PNG and q.get("inline") == "1" else "attachment"
            return 200, ctype, data, {
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(file_name)}",
                "Cache-Control": "no-store"}
        if method == "GET" and op in GET_JSON:
            result = JSON_OPS[op](q)
        elif method == "POST" and op in BODY_OPS:
            result = BODY_OPS[op](q, body)
        elif method == "POST" and op in JSON_OPS:
            payload = json.loads((body or b"{}").decode("utf-8"))
            result = JSON_OPS[op](payload)
        else:
            raise Refused("Unknown request.", 404)
    except Refused as exc:
        return exc.status, "application/json", json.dumps({"error": str(exc)}).encode(), {}
    except Exception as exc:
        traceback.print_exc()
        message = f"Something went wrong: {str(exc)[:200]}"
        return 500, "application/json", json.dumps({"error": message}).encode(), {}
    return 200, "application/json", json.dumps(result, default=_json_default,
                                               ensure_ascii=False).encode("utf-8"), {
        "Cache-Control": "no-store"}


def _json_default(value):
    if hasattr(value, "item"):           # numpy numbers from pandas
        return value.item()
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, (date,)):
        return value.isoformat()
    if value != value:                   # NaN
        return None
    raise TypeError(f"Can't send {type(value).__name__}")


class handler(BaseHTTPRequestHandler):
    """Vercel's Python runtime calls this class for /api/py."""

    def _respond(self, method):
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length) if length else b""
        status, ctype, data, extra = handle(method, self.path, self.headers, body)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in extra.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._respond("GET")

    def do_POST(self):
        self._respond("POST")
