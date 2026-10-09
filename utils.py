# -*- coding: utf-8 -*-
"""Small text, date and part-slot helpers."""
from datetime import date, datetime, timedelta
import unicodedata

from constants import (
    ASSISTANT_ROLES,
    AUX_HALL,
    AVAILABLE,
    CONFLICT,
    HALL_NAMES,
    MAIN_HALL,
    MIDWEEK,
    NEVER_BAND,
    PRIVILEGES,
    RESTING,
    STUDENT_ROLES,
    THIS_WEEK,
    WEEKEND,
)


# =============================================================================
# SMALL HELPERS
# =============================================================================
def nfc(text):
    return unicodedata.normalize("NFC", text or "").strip()


def fmt_date(iso, short=False):
    try:
        d = datetime.strptime(str(iso), "%Y-%m-%d").date()
    except ValueError:
        return str(iso)
    return f"{d.day} {d:%b}" if short else f"{d.day} {d:%B %Y}"


def month_label(ym):
    """'2026-10' -> 'October 2026'."""
    return datetime.strptime(ym, "%Y-%m").strftime("%B %Y")


def parse_privileges(value):
    """Turn the stored comma string into a clean list."""
    result = []
    for item in (value or "").split(","):
        item = item.strip()
        if item in PRIVILEGES and item not in result:
            result.append(item)
    return result


# Ga part titles, from the printed workbook. Checked before the English
# keywords because a Ga title matches none of them and would otherwise fall
# through to the section default, making every ministry part the same role.
GA_ROLE_WORDS = [
    ("biblia kanem", "Bible Reading"),
    ("biblia nikasem", "Bible Study Conductor"),      # Asafoŋ Biblia Nikasemɔ
    ("ŋmalɛi", "Spiritual Gems"),                     # Pɛimɔ Ŋmalɛi Lɛ Amli Jogbaŋŋ
    ("sanegbaa shishi", "Initial Presentation"),      # Kɛ́ Oyaaje Sanegbaa Shishi
    ("oyaatsa", "Initial Presentation"),              # Kɛ́ Oyaatsa Nɔ — following up
    ("obaakɛɛ", "Initial Presentation"),              # Mɛni Obaakɛɛ?
    ("kaselɔi", "Making Disciples"),                  # Kɛ́ Oofee Mɛi Kaselɔi
    ("gbalamɔ ohemɔkɛyeli", "Explaining Beliefs"),
]


# English words infer_role() keys on, kept beside the Ga list so a caller can
# ask whether a title actually named a part type or merely fell through.
EN_ROLE_WORDS = (
    "chairman", "prayer", "watchtower", "public talk", "reader", "bible study",
    "conductor", "bible reading", "gems", "treasures", "living", "disciple",
    "explaining", "belief", "presentation", "conversation", "following up", "talk",
)


def role_matched(title):
    """True when the title names a part type rather than taking the default."""
    t = nfc(title or "").lower()
    if t.strip(" .:") == "wiemɔ":          # a bare Ga "Talk", handled below
        return True
    if any(word in t for word, _ in GA_ROLE_WORDS):
        return True
    return any(word in t for word in EN_ROLE_WORDS)


def infer_role(title, section=None):
    t = nfc(title or "").lower()
    for word, role in GA_ROLE_WORDS:
        if word in t:
            return role
    if section == "Ministry" and t.strip(" .:") == "wiemɔ":   # a student talk
        return "Student Talk"
    if "chairman" in t:
        return "Chairman"
    if "prayer" in t:
        return "Prayer"
    if "watchtower" in t:
        return "Watchtower Reader"
    if "public talk" in t:
        return "Public Talk"
    if "reader" in t:
        return "Reader"
    if "bible study" in t or "conductor" in t:
        return "Bible Study Conductor"
    if "bible reading" in t:
        return "Bible Reading"
    if "gems" in t:
        return "Spiritual Gems"
    if "treasures" in t:
        return "Treasures Talk"
    if "living" in t:
        return "Living Part"
    if "disciple" in t:
        return "Making Disciples"
    if "explaining" in t or "belief" in t:
        return "Explaining Beliefs"
    if "presentation" in t or "conversation" in t or "following up" in t:
        return "Initial Presentation"
    if section == "Ministry":
        return "Student Talk" if "talk" in t else "Initial Presentation"
    if section == "Living":
        return "Living Part"
    return "Living Part"


def default_section(role, meeting_type=MIDWEEK):
    if meeting_type == WEEKEND:
        return "Weekend"
    if role in ("Chairman", "Aux Classroom Counselor"):
        return "Opening"
    if role in ("Treasures Talk", "Spiritual Gems", "Bible Reading"):
        return "Treasures"
    if role in STUDENT_ROLES:
        return "Ministry"
    return "Living"


def visitor_allowed(role, title, section=None):
    """Parts a visitor from another congregation may take, typed by hand
    instead of picked from the congregation's list: the public talk (with the
    closing prayer that goes with it). Every other part is a local brother."""
    return role == "Public Talk"


def make_slot(title, role, section, part_no=None, minutes=None, hall=MAIN_HALL):
    return {
        "hall": hall or MAIN_HALL,
        "allow_visitor": visitor_allowed(role, title, section),
        "part_no": part_no,
        "title": nfc(title),
        "role": role,
        "section": section,
        "minutes": minutes,
        "student_part": role in STUDENT_ROLES,
        "needs_assistant": role in ASSISTANT_ROLES,
    }


# ---------------------------------------------------------------------------
# Calendar weeks. A meeting week runs Monday to Sunday, as the workbook does,
# so "this week", "last week" and "next week" are fixed periods rather than
# "within 7 days": the Sunday before a Wednesday meeting is last week, the
# Sunday after it is later this week.
# ---------------------------------------------------------------------------
def as_date(value):
    """A date from a date or an ISO string (None if it isn't one)."""
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def week_start(day):
    """The Monday of the meeting week this day falls in."""
    day = as_date(day)
    return day - timedelta(days=day.weekday())


def weeks_apart(earlier, later):
    """Whole meeting weeks from one date's week to another's (0 = same week)."""
    return (week_start(later) - week_start(earlier)).days // 7


def week_label(day):
    """A fixed name for the meeting week, e.g. "Week 2 of October (5–11 Oct)".

    The week belongs to the month its Monday is in, so the week of
    28 September – 4 October is Week 5 of September; the dates printed beside
    it remove any doubt.
    """
    monday = week_start(day)
    sunday = monday + timedelta(days=6)
    number = (monday.day - 1) // 7 + 1
    span = (f"{monday.day}–{sunday.day} {sunday:%b}" if monday.month == sunday.month
            else f"{monday.day} {monday:%b} – {sunday.day} {sunday:%b}")
    return f"Week {number} of {monday:%B} ({span})"


def relative_week(other, meeting_date):
    """How another date's week relates to this meeting's week, in words:
    "this week", "last week", "next week", "3 weeks ago", "in 2 weeks"."""
    n = weeks_apart(meeting_date, other)
    if n == 0:
        return "this week"
    if n == -1:
        return "last week"
    if n == 1:
        return "next week"
    return f"{-n} weeks ago" if n < 0 else f"in {n} weeks"


def recency(last_date, meeting_date=None):
    """(marker, wording) for when someone last had a part, in meeting weeks
    before the meeting being scheduled.

    Counted from that meeting rather than from today: working on Week 3 of
    October, "last week" means Week 2 of October whenever you open it.
    """
    then = as_date(last_date) if last_date else None
    now = as_date(meeting_date) if meeting_date else date.today()
    if then is None or now is None:
        return NEVER_BAND
    if then > now:
        return CONFLICT[0], conflict_wording(then, now)
    weeks = weeks_apart(then, now)
    if weeks == 0:
        return THIS_WEEK
    if weeks == 1:
        return RESTING, "last week"
    return AVAILABLE, (f"{weeks} weeks ago" if weeks <= 4 else "over a month ago")


def conflict_wording(when, meeting_date):
    """How far after this meeting another assignment falls, with its date.

    Orange on its own only says "later"; whether that is this weekend or a
    month away changes whether it matters, so the wording spells it out.
    """
    when = as_date(when)
    span = relative_week(when, meeting_date)
    span = "later this week" if span == "this week" else span
    return f"{CONFLICT[1]} {span} ({when.day} {when:%b})"


def slot_label(slot, hall_names=None):
    """hall_names lets printed output name the room in the slip language;
    the interface passes nothing and gets English."""
    label = slot["title"]
    if slot.get("minutes") and "min" not in label.lower():
        label += f" ({slot['minutes']} min)"
    label = f"{slot['part_no']}. {label}" if slot.get("part_no") else label
    hall = slot.get("hall") or MAIN_HALL
    if hall != MAIN_HALL:
        names = hall_names or HALL_NAMES
        label += f" · {names.get(hall, HALL_NAMES.get(hall, hall))}"
    return label


def slot_match_key(slot):
    """Used to carry names across when the parts list is swapped."""
    hall = slot.get("hall") or MAIN_HALL
    if slot.get("part_no"):
        return (hall, slot["role"], slot["part_no"])
    return (hall, slot["role"], slot["title"].lower())


def apply_aux(slots, aux_on):
    """Add (or strip) the auxiliary-classroom counselor and a second slot per student part."""
    base = [s for s in slots
            if s.get("hall", MAIN_HALL) == MAIN_HALL and s["role"] != "Aux Classroom Counselor"]
    if not aux_on:
        return base
    out = []
    for s in base:
        out.append(s)
        if s["role"] == "Chairman":
            out.append(make_slot("Auxiliary Classroom Counselor",
                                 "Aux Classroom Counselor", s["section"]))
        if s["student_part"]:
            out.append(make_slot(s["title"], s["role"], s["section"],
                                 s["part_no"], s.get("minutes"), hall=AUX_HALL))
    return out


def fill_progress(slots, picks):
    """(filled, needed) for the parts on the page, counted slot by slot.

    picks holds (person, assistant) under each slot's index; a visitor's name
    sits under index + 10000 and his congregation under index + 20000. The
    congregation belongs to the name, so it is never a part of its own —
    counting it made "filled" run past "needed".
    """
    needed = filled = 0
    for i, slot in enumerate(slots):
        sid, aid = picks.get(i, (None, None))
        visitor = nfc(str(picks.get(i + 10000) or ""))
        needed += 1
        filled += int(sid is not None or bool(visitor))
        if slot["needs_assistant"]:
            needed += 1
            filled += int(aid is not None)
    return filled, needed

