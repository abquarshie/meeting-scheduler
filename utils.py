# -*- coding: utf-8 -*-
"""Small text, date and part-slot helpers."""
from datetime import date, datetime, timedelta
import re
import unicodedata

from constants import *  # noqa: F401,F403


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


def parse_privileges(value):
    """Turn the stored comma string into a clean list, upgrading legacy names."""
    result = []
    for item in (value or "").split(","):
        item = item.strip()
        for p in LEGACY_PRIVILEGES.get(item, [item]):
            if p in PRIVILEGES and p not in result:
                result.append(p)
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
    if "watchtower" in t and "reader" in t:
        return "Watchtower Reader"
    if "watchtower" in t:
        return "Watchtower Conductor"
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


def visitor_allowed(role, title):
    """Parts a visitor from another congregation may take, typed by hand
    instead of picked from the congregation's list: the public talk, and the
    closing prayer, which a visiting speaker is often asked to say."""
    if role == "Public Talk":
        return True
    return role == "Prayer" and nfc(title).lower().startswith("closing")


def make_slot(title, role, section, part_no=None, minutes=None, hall=MAIN_HALL):
    return {
        "hall": hall or MAIN_HALL,
        "allow_visitor": visitor_allowed(role, title),
        "part_no": part_no,
        "title": nfc(title),
        "role": role,
        "section": section,
        "minutes": minutes,
        "student_part": role in STUDENT_ROLES,
        "needs_assistant": role in ASSISTANT_ROLES,
    }


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
