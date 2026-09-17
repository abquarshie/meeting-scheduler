# -*- coding: utf-8 -*-
"""Fixed lists, roles and slip wording."""
import os
from pathlib import Path
import unicodedata

# =============================================================================
# CONSTANTS
# =============================================================================
APP_DIR = Path(__file__).resolve().parent
# MEETING_DB lets tests (or a second congregation) use another database file.
DEFAULT_DB = APP_DIR / "meeting_scheduler.db"


def db_path():
    return Path(os.environ.get("MEETING_DB") or DEFAULT_DB)

MIDWEEK = "Midweek Meeting"
WEEKEND = "Weekend Meeting"
MEETING_TYPES = [MIDWEEK, WEEKEND]
CATEGORIES = ["Brother", "Sister"]
GROUPS = ["Child", "Youth", "New student"]
GROUP_TAGS = {"Child": "child", "Youth": "youth", "New student": "new"}
NO_FAMILY = "— none —"

PRIVILEGES = [
    "Chairman",
    "Prayer",
    "Treasures Talk",
    "Spiritual Gems",
    "Bible Reading",
    "Initial Presentation",
    "Making Disciples",
    "Explaining Beliefs",
    "Student Talk",
    "Living Part",
    "Bible Study Conductor",
    "Reader",
    "Aux Classroom Counselor",
    "Weekend Chairman",
    "Public Talk",
    "Watchtower Conductor",
    "Watchtower Reader",
]
# Privilege names used by the first version of the app.
LEGACY_PRIVILEGES = {
    "Talk": ["Treasures Talk", "Spiritual Gems", "Student Talk", "Living Part"],
}

# role -> (privileges that qualify, brothers only)
ROLE_RULES = {
    "Chairman": ({"Chairman"}, True),
    "Prayer": ({"Prayer"}, True),
    "Treasures Talk": ({"Treasures Talk"}, True),
    "Spiritual Gems": ({"Spiritual Gems"}, True),
    "Bible Reading": ({"Bible Reading"}, True),
    "Initial Presentation": ({"Initial Presentation"}, False),
    "Making Disciples": ({"Making Disciples"}, False),
    "Explaining Beliefs": ({"Explaining Beliefs"}, False),
    "Student Talk": ({"Student Talk"}, True),
    "Living Part": ({"Living Part"}, True),
    "Bible Study Conductor": ({"Bible Study Conductor"}, True),
    "Reader": ({"Reader"}, True),
    "Aux Classroom Counselor": ({"Aux Classroom Counselor"}, True),
    "Weekend Chairman": ({"Weekend Chairman"}, True),
    "Public Talk": ({"Public Talk"}, True),
    "Watchtower Conductor": ({"Watchtower Conductor"}, True),
    "Watchtower Reader": ({"Watchtower Reader"}, True),
}
ROLES = list(ROLE_RULES)
STUDENT_ROLES = {
    "Bible Reading",
    "Initial Presentation",
    "Making Disciples",
    "Explaining Beliefs",
    "Student Talk",
}
ASSISTANT_ROLES = {"Initial Presentation", "Making Disciples", "Explaining Beliefs"}

MAIN_HALL, AUX_HALL = "main_hall", "aux_1"
HALL_NAMES = {MAIN_HALL: "Main hall", AUX_HALL: "Auxiliary classroom"}

SECTIONS = ["Opening", "Treasures", "Ministry", "Living", "Closing", "Weekend"]
SECTION_TITLES = {
    "Opening": "Opening",
    "Treasures": "Treasures From God’s Word",
    "Ministry": "Apply Yourself to the Field Ministry",
    "Living": "Living as Christians",
    "Closing": "Closing",
    "Weekend": "Weekend meeting",
}

GA_CHARS = "ɛɔŋƐƆŊ"

# NOTE: the Ga wording below only has its casing fixed. Replace it with the
# exact text printed on the official Ga S-89 so the slips match the paper form.
TRANSLATIONS = {
    "English": {
        "slip_title": "OUR CHRISTIAN LIFE AND MINISTRY\nMEETING ASSIGNMENT",
        "name": "Name:",
        "assistant": "Assistant:",
        "date": "Date:",
        "part_no": "Part no.:",
        "to_be_given": "To be given in:",
        "main_hall": "Main hall",
        "aux_1": "Auxiliary classroom 1",
        "aux_2": "Auxiliary classroom 2",
        "note": (
            "Note to student: The source material and study point for your"
            " assignment can be found in the Life and Ministry Meeting Workbook."
            " Please review the instructions for the part as outlined in"
            " Instructions for Our Christian Life and Ministry Meeting (S-38)."
        ),
        "form_code": "S-89-E 11/23",
    },
    "Ga": {
        "slip_title": "KRISTOWALA AMƐ WALA KƐ NITSUMƆ\nKPEENI NITSUMƆ",
        "name": "Gbɛi:",
        "assistant": "Mɔ ni yeo boa:",
        "date": "Gbi:",
        "part_no": "Nitsumɔ akara:",
        "to_be_given": "Abaatsɔo mli:",
        "main_hall": "Maŋ tsu nukpa",
        "aux_1": "Tsu bibioo 1",
        "aux_2": "Tsu bibioo 2",
        "note": (
            "Nilelɔ nɔ ni akɛɛ: Nitsumɔ lɛ he nibii kɛ nikasemɔ nɔ ni kɔ kɛhɔ bo"
            " lɛ baanyɛ aná yɛ Kristowala Amɛ Wala kɛ Nitsumɔ Kpeeni Wolo lɛ mli."
            " Ofainɛ kwɛmɔ nitsumɔ lɛ he gbɛtsɔɔmɔi ni yɔɔ Kristowala Amɛ Wala kɛ"
            " Nitsumɔ Kpeeni Gbɛtsɔɔmɔi (S-38) lɛ mli."
        ),
        "form_code": "S-89-Ga 11/23",
    },
}
TRANSLATIONS = {
    lang: {k: unicodedata.normalize("NFC", v) for k, v in strings.items()}
    for lang, strings in TRANSLATIONS.items()
}
