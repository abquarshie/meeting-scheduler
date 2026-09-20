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
    "Watchtower Conductor": "Buu Mɔɔ Nɔkwɛlɔ",
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

# Nobody takes the same part two meetings running: a chairman this week is
# given something else next week. Held to only when somebody else qualifies —
# a small congregation would otherwise leave the part empty.
SAME_ROLE_GAP_DAYS = 10

# How long since someone last had a part, as a coloured band. Streamlit's
# dropdowns take plain text, so the colour has to be a character.
# (days since, marker, wording)
# How recently someone had a part, counted in weeks back from the meeting being
# scheduled — not from today, so reopening an old week reads as it did then.
# (weeks before this one, marker, wording)
RECENCY_BANDS = [
    (1, "🔴", "last week"),
    (2, "🟡", "2 weeks ago"),
    (3, "🔵", "3 weeks ago"),
    (4, "🟢", "4 weeks ago"),
]
LONG_AGO = ("⚪", "over a month ago")
NEVER_BAND = ("⚪", "no parts yet")
THIS_WEEK = ("🔴", "this week")

GA_CHARS = "ɛɔŋƐƆŊ"

# NOTE: the Ga wording below only has its casing fixed. Replace it with the
# exact text printed on the official Ga S-89 so the slips match the paper form.
# Wording that appears on the printed schedule sheets. The slips are printed
# on the official blank S-89, so its own wording lives on that form and is not
# copied here.
TRANSLATIONS = {
    "English": {
        "main_hall": "Main hall",
        "aux_1": "Auxiliary classroom 1",
        "aux_2": "Auxiliary classroom 2",
        "midweek_meeting": "Midweek Meeting",
        "weekend_meeting": "Weekend Meeting",
    },
    "Ga": {
        "main_hall": "Asa 1",
        "aux_1": "Asa 2",
        "aux_2": "Asa 3",
        "midweek_meeting": "Wɔshiɛmɔ Kɛ Wɔshihilɛ Kpee",
        "weekend_meeting": "Otsi Naagbee Kpee",
    },
}
TRANSLATIONS = {
    lang: {k: unicodedata.normalize("NFC", v) for k, v in strings.items()}
    for lang, strings in TRANSLATIONS.items()
}
