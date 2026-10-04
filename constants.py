# -*- coding: utf-8 -*-
"""Fixed lists, roles and slip wording."""
from pathlib import Path
import unicodedata

# =============================================================================
# CONSTANTS
# =============================================================================
APP_DIR = Path(__file__).resolve().parent
# Storage is Postgres; see db.dsn() and db.schema() for how it is configured.

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

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
    "Watchtower Reader",
]
# Each part (role) is taken by people holding the privilege of the same name,
# so the two lists are one. Every part is for brothers only, apart from these.
ROLES = PRIVILEGES
SISTER_ROLES = {"Initial Presentation", "Making Disciples", "Explaining Beliefs"}
# Weeks with no regular meetings. Each shows a label wherever the week
# appears, in the language of the page or printout: TRANSLATIONS["event_…"].
EVENT_KINDS = ("assembly", "convention")
EVENT_NAMES = {"assembly": "Circuit Assembly", "convention": "Convention"}

# Roles the app no longer schedules. Saved assignments and privileges naming
# them are cleared at start-up (db.init_db), after a restore, and on undo.
REMOVED_ROLES = ("Watchtower Conductor",)
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
    "speaker": "Wielɔ",
    "reader": "Kanelɔ",
    "weekend_schedule": "Otsi Naagbee Kpee He Gbɛjianɔtoo",
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
    "speaker": "Speaker",
    "reader": "Reader",
    "weekend_schedule": "Weekend Meeting Schedule",
}
ROLE_LABELS = {
    "Prayer": "Prayer",
    "Chairman": "Chairman",
    "Weekend Chairman": "Chairman",
    "Bible Study Conductor": "Conductor",
    "Reader": "Reader",
    "Watchtower Reader": "Reader",
    "Aux Classroom Counselor": "Auxiliary Classroom Counselor",
}

# Nobody takes the same part two meetings running: a chairman this week is
# given something else next week. Held to only when somebody else qualifies —
# a small congregation would otherwise leave the part empty. This is only the
# default the first time the app runs — Admin → Settings can change the rest
# period without touching code; see db.same_role_gap_days().
SAME_ROLE_GAP_DAYS = 10

# How recently someone had a part, as a coloured marker (Streamlit's dropdowns
# take plain text, so the colour has to be a character). Counted back from the
# meeting being scheduled — not from today — so reopening an old week reads as
# it did then; see utils.recency().
#
# Two states, because the rotation has exactly one threshold: a turn this week
# or last week means a break, and after that you are available again. The
# exact distance is spelt out in words beside the name. Red is a nudge, not a
# rule; the fallback still fills a part rather than leave it empty.
RESTING = "🔴"
AVAILABLE = "🟢"
# A distinct marker rather than plain green: green elsewhere means "available
# and rested", but nobody has actually rested here — they've simply never
# served. Worth its own look, especially for spotting newer participants.
NEVER_BAND = ("⭐", "no parts yet")
THIS_WEEK = (RESTING, "this week")
# A person already assigned to something *after* this meeting reads as a
# scheduling conflict, not a rotation cooldown — a different problem from
# "had this last week", so it gets its own colour rather than sharing red.
CONFLICT = ("🟠", "already scheduled")

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
        "event_assembly": "Assembly Week",
        "event_convention": "Convention Week",
    },
    "Ga": {
        "main_hall": "Asa 1",
        "aux_1": "Asa 2",
        "aux_2": "Asa 3",
        "midweek_meeting": "Wɔshiɛmɔ Kɛ Wɔshihilɛ Kpee",
        "weekend_meeting": "Otsi Naagbee Kpee",
        "event_assembly": "Kpokpaa Nɔ Kpee Otsi",
        "event_convention": "Kpokpaa wulu Nɔ Kpee Otsi",
    },
}
TRANSLATIONS = {
    lang: {k: unicodedata.normalize("NFC", v) for k, v in strings.items()}
    for lang, strings in TRANSLATIONS.items()
}
