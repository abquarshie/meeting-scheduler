# -*- coding: utf-8 -*-
"""Fixed lists, roles and slip wording."""
import os
from pathlib import Path
import unicodedata

# =============================================================================
# CONSTANTS
# =============================================================================
APP_DIR = Path(__file__).resolve().parent
# Storage is Postgres; see db.dsn() and db.schema() for how it is configured.

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

# Halls, in the order the S-89 prints its tick boxes. The ids double as the
# TRANSLATIONS keys for each hall's printed name, so slips can loop over them.
HALLS = ["main_hall", "aux_1", "aux_2"]
MAIN_HALL, AUX_HALL = HALLS[0], HALLS[1]
HALL_NAMES = {
    "main_hall": "Main hall",
    "aux_1": "Auxiliary classroom 1",
    "aux_2": "Auxiliary classroom 2",
}
# the same rooms in a sentence ("You have a part in …")
HALL_WORDS = {
    "main_hall": "the main hall",
    "aux_1": "auxiliary classroom 1",
    "aux_2": "auxiliary classroom 2",
}

SECTIONS = ["Opening", "Treasures", "Ministry", "Living", "Closing", "Weekend"]
SECTION_TITLES = {
    "Opening": "Opening",
    "Treasures": "Treasures From God’s Word",
    "Ministry": "Apply Yourself to the Field Ministry",
    "Living": "Living as Christians",
    "Closing": "Closing",
    "Weekend": "Weekend meeting",
}

# Colour carries meaning only: these three mark the workbook sections.
SECTION_COLORS = {
    "Treasures": "#5B6770",   # slate, as in the workbook
    "Ministry": "#B7821F",    # ochre
    "Living": "#8E2A2A",      # maroon
    "Opening": "#8A94A0",
    "Closing": "#8A94A0",
    "Weekend": "#8A94A0",
}
# Roles printed in bold beside the name on the schedule sheet. Roles left out
# here show the name alone, as the printed form does.
# Printed role labels per slip language. A role with no entry prints the name
# with no label, which is right where the part title already names the role
# (the Ga sheet's "Buu Mɔɔ Nikasemɔ" row needs no "Conductor" beside it).
ROLE_LABELS_GA = {
    "Prayer": "Sɔlemɔ",
    "Chairman": "Sɛinɔtalɔ",
    "Weekend Chairman": "Sɛinɔtalɔ",
    "Reader": "Kanelɔ",
    "Watchtower Reader": "Kanelɔ",
    "Aux Classroom Counselor": "Ŋaawolɔ",
}
GA_WORDS = {
    "public_talk": "Maŋshiɛmɔ",
    "watchtower": "Buu Mɔɔ Nikasemɔ",
    "theme": "Saneyitso",
    "guest_speaker": "Wielɔ ni afɔ lɛ nine",
    "chairman": "Sɛinɔtalɔ",
    "opening_prayer": "Sɔlemɔ",
    "closing_prayer": "Sɔlemɔ",
    "group": "Kuu",
    "song": "Lala",
}
EN_WORDS = {
    "public_talk": "Public Talk",
    "watchtower": "Watchtower Study",
    "theme": "Theme",
    "guest_speaker": "Guest speaker",
    "chairman": "Chairman",
    "opening_prayer": "Opening Prayer",
    "closing_prayer": "Closing Prayer",
    "group": "Group",
    "song": "Song",
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
        "midweek_meeting": "Midweek Meeting",
        "weekend_meeting": "Weekend Meeting",
    },
    "Ga": {
        "slip_title": "WƆSHIƐMƆ KƐ WƆSHIHILƐ AKƐ KRISTOFOI\nKPEE ASAIMƐNT",
        "name": "Gbɛi:",
        "assistant": "Yelikɛbualɔ:",
        "date": "Gbi:",
        "part_no": "Nifeemɔ Ni Ji:",
        "to_be_given": "Obaafee yɛ:",
        "main_hall": "Asa 1",
        "aux_1": "Asa 2",
        "aux_2": "Asa 3",
        "note": (
            "Skulnyo lɛ akadi: Atsɔɔ wolo loo nɔ kroko ni okɛbaatsu onifeemɔ lɛ"
            " he nii, kɛ nikasemɔ ni esa akɛ otsu he nii lɛ yɛ Wɔshɛimɔ Kɛ"
            " Wɔshihilɛ Kpee Nifeemɔ Wolo lɛ mli. Ofainɛ kanemɔ onifeemɔ lɔ he"
            " gbɛtsɔɔmɔi ni yɔɔ Wɔshɛimɔ Kɛ Wɔshihilɛ Kpee Nifeemɔ Wolo lɛ mli."
        ),
        "form_code": "",
        "midweek_meeting": "Wɔshiŋmɔ Kɛ Wɔshihilɛ Kpee",
        "weekend_meeting": "Otsi Naagbee Kpee",
    },
}
TRANSLATIONS = {
    lang: {k: unicodedata.normalize("NFC", v) for k, v in strings.items()}
    for lang, strings in TRANSLATIONS.items()
}
