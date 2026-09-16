# -*- coding: utf-8 -*-
"""Meeting Scheduler: midweek/weekend assignments, S-89 slips and S-140 export."""

from contextlib import contextmanager
from datetime import date, datetime
import io
import json
from pathlib import Path
import re
import sqlite3
import unicodedata
from xml.sax.saxutils import escape as xml_escape

import pandas as pd
import pypdf
from reportlab.lib import colors
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
import streamlit as st

from s140 import S140Error, fill_s140

st.set_page_config(page_title="Meeting Scheduler", page_icon="📅", layout="wide")

# Colours live in .streamlit/config.toml; only the stat cards need custom CSS.
st.markdown(
    """
    <style>
    .status-panel {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 15px;
        text-align: center;
    }
    .status-panel p { margin: 0; color: #8b949e; font-weight: bold; }
    .status-panel h3 { margin-top: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# CONSTANTS
# =============================================================================
APP_DIR = Path(__file__).parent
DB_FILE = APP_DIR / "meeting_scheduler.db"

MIDWEEK = "Midweek Meeting"
WEEKEND = "Weekend Meeting"
MEETING_TYPES = [MIDWEEK, WEEKEND]
CATEGORIES = ["Brother", "Sister"]

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
    "Opening": "🔹 Opening",
    "Treasures": "💎 Treasures From God's Word",
    "Ministry": "🌾 Apply Yourself to the Field Ministry",
    "Living": "🏠 Living as Christians",
    "Closing": "🙏 Closing",
    "Weekend": "🏛️ Weekend Meeting",
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


def infer_role(title, section=None):
    t = (title or "").lower()
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


def make_slot(title, role, section, part_no=None, minutes=None, hall=MAIN_HALL):
    return {
        "hall": hall or MAIN_HALL,
        "part_no": part_no,
        "title": nfc(title),
        "role": role,
        "section": section,
        "minutes": minutes,
        "student_part": role in STUDENT_ROLES,
        "needs_assistant": role in ASSISTANT_ROLES,
    }


def slot_label(slot):
    label = slot["title"]
    if slot.get("minutes") and "min" not in label.lower():
        label += f" ({slot['minutes']} min)"
    label = f"{slot['part_no']}. {label}" if slot.get("part_no") else label
    if slot.get("hall") == AUX_HALL:
        label += " · Auxiliary classroom"
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


# =============================================================================
# DATABASE
# =============================================================================
@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _add_missing_columns(conn, table, columns):
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                gender TEXT,
                privileges TEXT
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_date TEXT,
                meeting_type TEXT,
                part_name TEXT,
                assigned_person TEXT
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                meeting_date TEXT NOT NULL,
                meeting_type TEXT NOT NULL,
                heading TEXT,
                opening_song TEXT,
                middle_song TEXT,
                closing_song TEXT,
                PRIMARY KEY (meeting_date, meeting_type)
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )""")
        # Upgrade databases created by the first version of the app.
        _add_missing_columns(conn, "students", {"active": "INTEGER DEFAULT 1"})
        _add_missing_columns(conn, "schedules", {
            "part_no": "INTEGER",
            "minutes": "INTEGER",
            "section": "TEXT",
            "role": "TEXT",
            "student_part": "INTEGER DEFAULT 0",
            "needs_assistant": "INTEGER DEFAULT 0",
            "student_id": "INTEGER",
            "assistant_id": "INTEGER",
            "assistant_name": "TEXT",
            "sort_order": "INTEGER DEFAULT 0",
            "hall": "TEXT DEFAULT 'main_hall'",
        })
        _add_missing_columns(conn, "meetings", {"aux": "INTEGER"})
        conn.execute("UPDATE schedules SET hall = 'main_hall' WHERE hall IS NULL")
        conn.execute("UPDATE students SET active = 1 WHERE active IS NULL")
        conn.execute("""
            UPDATE schedules
               SET student_id = (SELECT s.id FROM students s
                                  WHERE s.name = schedules.assigned_person LIMIT 1)
             WHERE student_id IS NULL AND assigned_person IS NOT NULL""")
        legacy = conn.execute(
            "SELECT id, part_name, meeting_type FROM schedules WHERE role IS NULL"
        ).fetchall()
        for row_id, part_name, meeting_type in legacy:
            role = infer_role(part_name)
            section = default_section(role, meeting_type)
            if role == "Prayer" and meeting_type != WEEKEND:
                section = "Closing" if "clos" in (part_name or "").lower() else "Opening"
            conn.execute(
                """UPDATE schedules SET role = ?, section = COALESCE(section, ?),
                       student_part = ?, needs_assistant = ?, sort_order = id
                   WHERE id = ?""",
                (role, section, int(role in STUDENT_ROLES),
                 int(role in ASSISTANT_ROLES), row_id),
            )


def get_setting(key, default=""):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_students(active_only=False):
    query = "SELECT id, name, gender, privileges, active FROM students"
    if active_only:
        query += " WHERE active = 1"
    with get_conn() as conn:
        df = pd.read_sql(query + " ORDER BY name COLLATE NOCASE", conn)
    df["privilege_list"] = df["privileges"].apply(parse_privileges)
    return df


def add_student(name, gender, privileges):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO students (name, gender, privileges, active) VALUES (?, ?, ?, 1)",
            (nfc(name), gender, ", ".join(privileges)),
        )


def update_student(student_id, name, gender, privileges, active):
    with get_conn() as conn:
        conn.execute(
            "UPDATE students SET name = ?, gender = ?, privileges = ?, active = ? WHERE id = ?",
            (nfc(name), gender, ", ".join(privileges), int(active), student_id),
        )
        # keep the name snapshot on old schedules in step with the rename
        conn.execute("UPDATE schedules SET assigned_person = ? WHERE student_id = ?",
                     (nfc(name), student_id))
        conn.execute("UPDATE schedules SET assistant_name = ? WHERE assistant_id = ?",
                     (nfc(name), student_id))


def student_usage_count(student_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM schedules WHERE student_id = ? OR assistant_id = ?",
            (student_id, student_id),
        ).fetchone()[0]


def delete_student(student_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))


def get_schedules():
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT sc.id, sc.meeting_date, sc.meeting_type, sc.part_no, sc.part_name,
                   sc.minutes, sc.section, sc.role, sc.student_part, sc.needs_assistant,
                   sc.student_id, sc.assistant_id, sc.sort_order,
                   COALESCE(sc.hall, 'main_hall') AS hall,
                   COALESCE(s.name, sc.assigned_person) AS person,
                   COALESCE(a.name, sc.assistant_name) AS assistant
              FROM schedules sc
              LEFT JOIN students s ON s.id = sc.student_id
              LEFT JOIN students a ON a.id = sc.assistant_id
             ORDER BY sc.meeting_date DESC, sc.meeting_type, sc.sort_order, sc.id
            """,
            conn,
        )
    # NaN is truthy, so turn missing names into None for simple `or` checks.
    for col in ("person", "assistant"):
        df[col] = df[col].astype(object).where(df[col].notna(), None)
    return df


def saved_meetings(schedules_df):
    """[(date, type), ...] newest first."""
    if schedules_df.empty:
        return []
    pairs = schedules_df[["meeting_date", "meeting_type"]].drop_duplicates()
    return list(pairs.itertuples(index=False, name=None))


def meeting_label(pair):
    return f"{fmt_date(pair[0])} · {pair[1]}"


def load_schedule(meeting_date, meeting_type, schedules_df=None):
    df = get_schedules() if schedules_df is None else schedules_df
    rows = df[(df["meeting_date"] == str(meeting_date)) & (df["meeting_type"] == meeting_type)]
    slots, picks = [], {}
    for _, r in rows.iterrows():
        role = r["role"] or infer_role(r["part_name"])
        part_no = int(r["part_no"]) if pd.notna(r["part_no"]) else None
        minutes = int(r["minutes"]) if pd.notna(r["minutes"]) else None
        section = r["section"] or default_section(role, meeting_type)
        slot = make_slot(r["part_name"], role, section, part_no, minutes, r["hall"])
        slots.append(slot)
        sid = int(r["student_id"]) if pd.notna(r["student_id"]) else None
        aid = int(r["assistant_id"]) if pd.notna(r["assistant_id"]) else None
        picks[slot_match_key(slot)] = (sid, aid)
    return slots, picks


def get_meeting_meta(meeting_date, meeting_type):
    with get_conn() as conn:
        row = conn.execute(
            """SELECT heading, opening_song, middle_song, closing_song, aux FROM meetings
               WHERE meeting_date = ? AND meeting_type = ?""",
            (str(meeting_date), meeting_type),
        ).fetchone()
    keys = ["heading", "opening_song", "middle_song", "closing_song", "aux"]
    meta = dict(zip(keys, row)) if row else {k: "" for k in keys[:-1]}
    meta.setdefault("aux", None)
    return meta


def save_schedule(meeting_date, meeting_type, slots, picks, meta, names):
    """Replace everything stored for this date + meeting type."""
    rows = []
    for order, slot in enumerate(slots):
        sid, aid = picks.get(order, (None, None))
        rows.append((
            str(meeting_date), meeting_type, slot["part_no"], slot["title"],
            slot.get("minutes"), slot["section"], slot["role"],
            int(slot["student_part"]), int(slot["needs_assistant"]),
            sid, names.get(sid), aid, names.get(aid), order,
            slot.get("hall") or MAIN_HALL,
        ))
    with get_conn() as conn:
        conn.execute("DELETE FROM schedules WHERE meeting_date = ? AND meeting_type = ?",
                     (str(meeting_date), meeting_type))
        conn.executemany(
            """INSERT INTO schedules (meeting_date, meeting_type, part_no, part_name,
                   minutes, section, role, student_part, needs_assistant, student_id,
                   assigned_person, assistant_id, assistant_name, sort_order, hall)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.execute(
            """INSERT INTO meetings (meeting_date, meeting_type, heading, opening_song,
                   middle_song, closing_song, aux) VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(meeting_date, meeting_type) DO UPDATE SET
                   heading = excluded.heading, opening_song = excluded.opening_song,
                   middle_song = excluded.middle_song, closing_song = excluded.closing_song,
                   aux = excluded.aux""",
            (str(meeting_date), meeting_type, meta.get("heading", ""),
             meta.get("opening_song", ""), meta.get("middle_song", ""),
             meta.get("closing_song", ""), int(bool(meta.get("aux")))),
        )


def delete_schedule(meeting_date, meeting_type):
    with get_conn() as conn:
        conn.execute("DELETE FROM schedules WHERE meeting_date = ? AND meeting_type = ?",
                     (str(meeting_date), meeting_type))
        conn.execute("DELETE FROM meetings WHERE meeting_date = ? AND meeting_type = ?",
                     (str(meeting_date), meeting_type))


def last_assignment_dates(exclude_date):
    """student_id -> most recent meeting date they had a part or assisted."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT pid, MAX(meeting_date) FROM (
                   SELECT student_id AS pid, meeting_date FROM schedules
                    WHERE student_id IS NOT NULL AND meeting_date != ?
                   UNION ALL
                   SELECT assistant_id, meeting_date FROM schedules
                    WHERE assistant_id IS NOT NULL AND meeting_date != ?
               ) GROUP BY pid""",
            (str(exclude_date), str(exclude_date)),
        ).fetchall()
    return {pid: d for pid, d in rows}


# =============================================================================
# DEFAULT PART LISTS
# =============================================================================
def default_midweek_parts():
    """The numbered parts only (what a brochure would supply)."""
    return [
        make_slot("Treasures Talk", "Treasures Talk", "Treasures", 1, 10),
        make_slot("Spiritual Gems", "Spiritual Gems", "Treasures", 2, 10),
        make_slot("Bible Reading", "Bible Reading", "Treasures", 3, 4),
        make_slot("Initial Presentation", "Initial Presentation", "Ministry", 4, 3),
        make_slot("Making Disciples", "Making Disciples", "Ministry", 5, 4),
        make_slot("Explaining Your Beliefs", "Explaining Beliefs", "Ministry", 6, 5),
        make_slot("Living Part", "Living Part", "Living", 7, 15),
        make_slot("Congregation Bible Study", "Bible Study Conductor", "Living", 8, 30),
    ]


def build_midweek_slots(parts):
    """Wrap the numbered parts with the fixed roles every week needs."""
    slots = [
        make_slot("Chairman", "Chairman", "Opening"),
        make_slot("Opening Prayer", "Prayer", "Opening"),
    ]
    reader_added = False
    for part in parts:
        slots.append(dict(part))
        if part["role"] == "Bible Study Conductor":
            slots.append(make_slot("Congregation Bible Study Reader", "Reader", "Living"))
            reader_added = True
    if not reader_added:
        slots.append(make_slot("Congregation Bible Study Reader", "Reader", "Living"))
    slots.append(make_slot("Closing Prayer", "Prayer", "Closing"))
    return slots


def default_weekend_slots():
    return [
        make_slot("Chairman", "Chairman", "Weekend"),
        make_slot("Opening Prayer", "Prayer", "Weekend"),
        make_slot("Public Talk Speaker", "Public Talk", "Weekend"),
        make_slot("Watchtower Conductor", "Watchtower Conductor", "Weekend"),
        make_slot("Watchtower Reader", "Watchtower Reader", "Weekend"),
        make_slot("Closing Prayer", "Prayer", "Weekend"),
    ]


# =============================================================================
# BROCHURE PARSER
# =============================================================================
MONTHS = ("JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|"
          "SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER")
# Week headings are printed in capitals, e.g. "SEPTEMBER 29–OCTOBER 5".
WEEK_RE = re.compile(
    rf"\b(?:{MONTHS})\s+\d{{1,2}}\s*[-–—]\s*(?:(?:{MONTHS})\s+)?\d{{1,2}}\b"
)
# "4. Starting a Conversation (3 min.)" - the duration may sit on the next line.
PART_RE = re.compile(
    r"^[ \t]*(\d{1,2})\.[ \t]+([^\n]{2,90}?)[ \t]*\n?[ \t]*"
    r"\((?:(\d{1,2})[ \t]*min\.?|min\.?[ \t]*(\d{1,2}))\)",
    re.MULTILINE | re.IGNORECASE,
)
SONG_RE = re.compile(r"\b(?:Song|Lala)\s+(\d{1,3})\b", re.IGNORECASE)
HEADING_RES = {
    "Treasures": re.compile(r"TREASURES FROM GOD", re.IGNORECASE),
    "Ministry": re.compile(r"APPLY YOURSELF TO THE FIELD MINISTRY", re.IGNORECASE),
    "Living": re.compile(r"LIVING AS CHRISTIANS", re.IGNORECASE),
}


def _classify(part_no, title, minutes, section):
    if section is None:
        # No English headings found (e.g. another language): guess from numbers.
        if part_no <= 3:
            section = "Treasures"
        elif minutes is not None and minutes >= 30 or "bible study" in title.lower():
            section = "Living"
        else:
            section = None  # decided by the caller
    if section == "Treasures":
        role = {1: "Treasures Talk", 2: "Spiritual Gems"}.get(part_no, "Bible Reading")
    elif section == "Living":
        is_cbs = "bible study" in title.lower() or (minutes or 0) >= 30
        role = "Bible Study Conductor" if is_cbs else "Living Part"
    elif section == "Ministry":
        role = infer_role(title, "Ministry")
        if role not in STUDENT_ROLES:
            role = "Student Talk" if "talk" in title.lower() else "Initial Presentation"
    else:
        role = None
    return section, role


def _parse_week(text):
    heading_hits = sorted(
        (m.start(), name) for name, rx in HEADING_RES.items() for m in rx.finditer(text)
    )
    parts, seen = [], set()
    in_living = False
    for m in PART_RE.finditer(text):
        part_no = int(m.group(1))
        if part_no in seen:
            continue
        seen.add(part_no)
        title = re.sub(r"\s+", " ", m.group(2)).strip(" .–—-\"“”")
        minutes = int(m.group(3) or m.group(4))
        section = None
        for pos, name in heading_hits:
            if pos < m.start():
                section = name
        section, role = _classify(part_no, title, minutes, section)
        if section is None:
            # Heuristic: short parts after 3 are student parts until a longer one.
            if not in_living and minutes <= 5:
                section = "Ministry"
            else:
                in_living = True
                section = "Living"
            section, role = _classify(part_no, title, minutes, section)
        parts.append(make_slot(title, role, section, part_no, minutes))
    parts.sort(key=lambda p: p["part_no"])
    songs = SONG_RE.findall(text)[:3]
    return parts, songs


@st.cache_data(show_spinner="Reading brochure…")
def parse_brochure(pdf_bytes):
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages = [nfc(page.extract_text() or "") for page in reader.pages]
    full_text = "\n".join(pages)

    chunks = {}
    matches = list(WEEK_RE.finditer(full_text))
    if matches:
        for i, m in enumerate(matches):
            label = re.sub(r"\s*[-–—]\s*", "–", re.sub(r"\s+", " ", m.group(0)))
            end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
            chunks[label] = chunks.get(label, "") + "\n" + full_text[m.start():end]
    else:
        for i, text in enumerate(pages):
            chunks[f"Workbook page {i + 1}"] = text

    weeks, empty = {}, []
    for label, text in chunks.items():
        parts, songs = _parse_week(text)
        if parts:
            weeks[label] = {"parts": parts, "songs": songs}
        else:
            empty.append(label)
    raw = "\n".join(f"--- Page {i + 1} ---\n{t}" for i, t in enumerate(pages))
    return weeks, empty, raw


# =============================================================================
# PDF OUTPUT
# =============================================================================
FONT_DIR = APP_DIR / "fonts"
FONT_CANDIDATES = [
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
            return "[X]" if filled and key == row.get("hall", MAIN_HALL) else "[&nbsp;&nbsp;]"

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
                f"{tick('main_hall')} {xml_escape(lang['main_hall'])}<br/>"
                f"{tick('aux_1')} {xml_escape(lang['aux_1'])}<br/>"
                f"{tick('aux_2')} {xml_escape(lang['aux_2'])}",
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
                data.append([Paragraph(xml_escape(SECTION_TITLES.get(section, section)
                                                  .split(" ", 1)[-1]), sec_style), ""])
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
        aux_week = bool(meta.get("aux")) or (rows["hall"] == AUX_HALL).any()
        for _, r in rows.iterrows():
            title = re.sub(r"\s*\(\s*\d+\s*min\.?\s*\)\s*$", "", r["part_name"] or "",
                           flags=re.IGNORECASE)
            item = {"title": title,
                    "min": str(int(r["minutes"])) if pd.notna(r["minutes"]) else "",
                    "name": r["person"] or ""}
            role, section = r["role"], r["section"]
            if r["hall"] == AUX_HALL:
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


# =============================================================================
# ASSIGNMENT PICKER HELPERS
# =============================================================================
def eligible_ids(role, students, show_all):
    active = students[students["active"] == 1]
    if show_all or role not in ROLE_RULES:
        return active["id"].tolist()
    privileges, brothers_only = ROLE_RULES[role]
    mask = active["privilege_list"].apply(lambda p: bool(privileges & set(p)))
    if brothers_only:
        mask &= active["gender"] == "Brother"
    return active[mask]["id"].tolist()


def ordered_options(ids, last_dates, keep=None):
    """Least recently used first, with the current pick always included."""
    ids = list(dict.fromkeys(ids))
    if keep is not None and keep not in ids:
        ids.append(keep)
    ids.sort(key=lambda i: last_dates.get(i) or "")
    return [None] + ids


def person_label_factory(students, last_dates):
    names = dict(zip(students["id"], students["name"]))
    inactive = set(students[students["active"] != 1]["id"])

    def label(pid):
        if pid is None:
            return "-- Unassigned --"
        last = last_dates.get(pid)
        suffix = f"last: {fmt_date(last, short=True)}" if last else "no parts yet"
        flag = " · inactive" if pid in inactive else ""
        return f"{names.get(pid, '?')} ({suffix}{flag})"

    return label


# =============================================================================
# APP
# =============================================================================
init_db()
FONT_REGULAR, FONT_BOLD, FONT_SUPPORTS_GA = register_fonts()


def go(page, **state):
    st.session_state["menu"] = page
    for k, v in state.items():
        st.session_state[k] = v
    st.rerun()


if "menu" not in st.session_state:
    st.session_state["menu"] = "Dashboard"

selected_lang = st.sidebar.selectbox("Slip language", list(TRANSLATIONS))
t = TRANSLATIONS[selected_lang]
if selected_lang != "English" and not FONT_SUPPORTS_GA:
    st.sidebar.warning(
        "No font with ɛ, ɔ and ŋ was found, so Ga slips will show boxes. "
        "Put DejaVuSans.ttf and DejaVuSans-Bold.ttf in a 'fonts' folder next to app.py."
    )
aux_setting = get_setting("use_aux", "1") == "1"
aux_default = st.sidebar.toggle(
    "Auxiliary classroom in use", value=aux_setting,
    help="Default for new midweek schedules. Any single week can still be switched off.",
)
if aux_default != aux_setting:
    set_setting("use_aux", "1" if aux_default else "0")
st.sidebar.markdown("---")
if st.sidebar.button("🏠 Back to Dashboard", width="stretch"):
    go("Dashboard")

menu = st.session_state["menu"]
students_df = get_students()

# -----------------------------------------------------------------------------
if menu == "Dashboard":
    st.title("📅 Meeting Scheduler")
    st.write("Manage assignments and participants, and print slips and schedules.")
    st.markdown("---")

    c1, c2, c3 = st.columns(3)
    if c1.button("📋 View Schedules & Slips", width="stretch"):
        go("View Schedules")
    if c2.button("📝 Create Schedule", width="stretch"):
        go("Schedule", schedule_mode="Create new")
    if c3.button("✏️ Modify Schedule", width="stretch"):
        go("Schedule", schedule_mode="Edit saved")

    c4, c5, c6 = st.columns(3)
    if c4.button("📖 Upload Workbook PDF", width="stretch"):
        go("Upload PDF Brochure")
    if c5.button("👥 Manage Participants", width="stretch"):
        go("Manage Participants")
    if c6.button("📤 Export (CSV / S-140)", width="stretch"):
        go("Export")

    if st.button("🔄 Reset session (clears uploaded brochure and filters)"):
        st.session_state.clear()
        st.rerun()

    st.markdown("---")
    schedules_df = get_schedules()
    today = date.today().isoformat()
    upcoming = sorted(d for d in schedules_df["meeting_date"].unique() if d >= today)
    focus_date = upcoming[0] if upcoming else (
        schedules_df["meeting_date"].max() if not schedules_df.empty else None)
    focus_label = "Next Meeting" if upcoming else "Latest Schedule"
    open_parts = 0
    if focus_date:
        focus_rows = schedules_df[schedules_df["meeting_date"] == focus_date]
        open_parts = int(focus_rows["student_id"].isna().sum()) + int(
            ((focus_rows["needs_assistant"] == 1) & focus_rows["assistant_id"].isna()).sum()
        )
    active_count = int((students_df["active"] == 1).sum())
    open_color = "#3fb950" if open_parts == 0 else "#d29922"

    s1, s2, s3 = st.columns(3)
    s1.markdown(f"""<div class="status-panel"><p>{focus_label}</p>
        <h3 style="color:#c9d1d9;">{fmt_date(focus_date) if focus_date else "None yet"}</h3>
        </div>""", unsafe_allow_html=True)
    s2.markdown(f"""<div class="status-panel"><p>Open Slots ({focus_label.lower()})</p>
        <h3 style="color:{open_color};">{open_parts if focus_date else "—"}</h3>
        </div>""", unsafe_allow_html=True)
    s3.markdown(f"""<div class="status-panel"><p>Active Participants</p>
        <h3 style="color:#58a6ff;">{active_count}</h3></div>""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
elif menu == "Manage Participants":
    st.header("👥 Participants")
    tab_add, tab_edit, tab_list = st.tabs(["Add", "Edit / deactivate", "List"])

    with tab_add:
        with st.form("add_student_form", clear_on_submit=True):
            name = st.text_input("Full name")
            gender = st.selectbox("Category", CATEGORIES)
            privileges = st.multiselect("Privileges", PRIVILEGES)
            if st.form_submit_button("Add participant"):
                if not nfc(name):
                    st.error("Enter a name.")
                else:
                    if nfc(name).lower() in students_df["name"].str.lower().tolist():
                        st.warning(f"There is already someone called {name}; added anyway.")
                    add_student(name, gender, privileges)
                    st.success(f"Added {name}.")
                    st.rerun()

    with tab_edit:
        if students_df.empty:
            st.info("No participants yet.")
        else:
            names = dict(zip(students_df["id"], students_df["name"]))
            sid = st.selectbox(
                "Participant", students_df["id"].tolist(),
                format_func=lambda i: names[i]
                + ("" if students_df.loc[students_df["id"] == i, "active"].iloc[0] == 1
                   else " (inactive)"),
            )
            row = students_df[students_df["id"] == sid].iloc[0]
            with st.form(f"edit_student_{sid}"):
                e_name = st.text_input("Full name", row["name"])
                e_gender = st.selectbox(
                    "Category", CATEGORIES,
                    index=CATEGORIES.index(row["gender"]) if row["gender"] in CATEGORIES else 0,
                )
                e_priv = st.multiselect("Privileges", PRIVILEGES, default=row["privilege_list"])
                e_active = st.checkbox("Active (shown when assigning parts)",
                                       value=bool(row["active"]))
                if st.form_submit_button("Save changes"):
                    if not nfc(e_name):
                        st.error("Name can't be empty.")
                    else:
                        update_student(sid, e_name, e_gender, e_priv, e_active)
                        st.success("Saved. Existing schedules show the updated name.")
                        st.rerun()

            used = student_usage_count(sid)
            with st.expander("Delete permanently"):
                if used:
                    st.info(
                        f"{row['name']} appears in {used} saved assignment(s). "
                        "Untick 'Active' instead so the history stays intact."
                    )
                elif st.button("Delete participant", type="primary"):
                    delete_student(sid)
                    st.warning("Participant deleted.")
                    st.rerun()

    with tab_list:
        if students_df.empty:
            st.info("No participants yet.")
        else:
            last = last_assignment_dates(exclude_date="")
            view = students_df.assign(
                last_assignment=students_df["id"].map(
                    lambda i: fmt_date(last[i]) if i in last else ""),
                status=students_df["active"].map({1: "Active"}).fillna("Inactive"),
                privileges=students_df["privilege_list"].apply(", ".join),
            )[["name", "gender", "privileges", "last_assignment", "status"]]
            st.dataframe(view, width="stretch", hide_index=True)

# -----------------------------------------------------------------------------
elif menu == "Schedule":
    st.header("📝 Create or Edit a Schedule")
    schedules_df = get_schedules()
    meetings = saved_meetings(schedules_df)

    mode = st.radio("Mode", ["Create new", "Edit saved"], horizontal=True,
                    key="schedule_mode")
    if mode == "Edit saved":
        if not meetings:
            st.info("No saved schedules yet.")
            st.stop()
        if st.session_state.get("edit_meeting") not in meetings:
            st.session_state.pop("edit_meeting", None)
        meeting_date, meeting_type = st.selectbox(
            "Saved schedule", meetings, format_func=meeting_label, key="edit_meeting")
    else:
        c1, c2 = st.columns(2)
        meeting_type = c1.selectbox("Meeting type", MEETING_TYPES)
        meeting_date = c2.date_input("Meeting date", value=date.today()).isoformat()

    saved_slots, saved_picks = load_schedule(meeting_date, meeting_type, schedules_df)
    meta = get_meeting_meta(meeting_date, meeting_type)
    if saved_slots and mode == "Create new":
        st.info("A schedule is already saved for this date. It's loaded below, "
                "and saving will replace it.")

    brochure = st.session_state.get("brochure_weeks", {})
    source = "saved" if saved_slots else "default"
    slots = saved_slots or (
        build_midweek_slots(default_midweek_parts())
        if meeting_type == MIDWEEK else default_weekend_slots())

    if meeting_type == MIDWEEK and brochure:
        use_brochure = st.checkbox(
            "Use parts from the uploaded workbook", value=not saved_slots,
            help="Names already picked carry over when the part number and role match.",
        )
        if use_brochure:
            week = st.selectbox("Workbook week", list(brochure))
            slots = build_midweek_slots(brochure[week]["parts"])
            source = f"brochure:{week}"
            songs = brochure[week].get("songs", [])
            if not saved_slots:
                meta = {
                    "heading": week,
                    "opening_song": f"Song {songs[0]}" if len(songs) > 0 else "",
                    "middle_song": f"Song {songs[1]}" if len(songs) > 1 else "",
                    "closing_song": f"Song {songs[2]}" if len(songs) > 2 else "",
                }
    elif meeting_type == MIDWEEK:
        st.caption("Tip: upload the workbook PDF to fill in this week's real part titles.")

    aux_on = False
    if meeting_type == MIDWEEK:
        saved_aux = meta.get("aux")
        aux_on = st.checkbox(
            "Auxiliary classroom this week",
            value=bool(saved_aux) if saved_aux is not None else aux_default,
            key=f"{meeting_date}|{meeting_type}|aux",
            help="Adds a counselor and a second student (and assistant) for the "
                 "Bible reading and each field-ministry part.",
        )
    slots = apply_aux(slots, aux_on)

    active = students_df[students_df["active"] == 1]
    if active.empty:
        st.warning("Add participants under 'Manage Participants' first.")
        st.stop()

    show_all = st.checkbox("Show everyone in every list (ignore privileges and category)")
    last_dates = last_assignment_dates(meeting_date)
    label = person_label_factory(students_df, last_dates)
    categories = dict(zip(students_df["id"], students_df["gender"]))
    names = dict(zip(students_df["id"], students_df["name"]))

    ns = f"{meeting_date}|{meeting_type}|{source}"
    with st.expander("Meeting details (used on the S-140)", expanded=False):
        m1, m2 = st.columns(2)
        meta_in = {
            "heading": m1.text_input("Heading", meta.get("heading", ""), key=f"{ns}|heading"),
            "opening_song": m2.text_input("Opening song", meta.get("opening_song", ""),
                                          key=f"{ns}|song1"),
            "middle_song": m1.text_input("Middle song", meta.get("middle_song", ""),
                                         key=f"{ns}|song2"),
            "closing_song": m2.text_input("Closing song", meta.get("closing_song", ""),
                                          key=f"{ns}|song3"),
            "aux": aux_on,
        }

    picks, current_section = {}, None
    for i, slot in enumerate(slots):
        if slot["section"] != current_section:
            current_section = slot["section"]
            st.markdown(f"#### {SECTION_TITLES.get(current_section, current_section)}")
        pre_sid, pre_aid = saved_picks.get(slot_match_key(slot), (None, None))
        options = ordered_options(eligible_ids(slot["role"], students_df, show_all),
                                  last_dates, keep=pre_sid)
        wkey = f"{ns}|{slot['hall']}|{slot['role']}|{slot['part_no']}|{slot['title']}"
        text = slot_label(slot)
        if aux_on and slot["student_part"] and slot["hall"] == MAIN_HALL:
            text += " · Main hall"
        cols = st.columns([3, 2]) if slot["needs_assistant"] else [st.container()]
        sid = cols[0].selectbox(
            text, options, index=options.index(pre_sid),
            format_func=label, key=f"{wkey}|student",
        )
        aid = None
        if slot["needs_assistant"]:
            pool = active["id"].tolist()
            if sid is not None and not show_all:
                pool = [p for p in pool if categories.get(p) == categories.get(sid)]
            pool = [p for p in pool if p != sid]
            a_options = ordered_options(pool, last_dates, keep=pre_aid)
            aid = cols[1].selectbox(
                "Assistant", a_options, index=a_options.index(pre_aid),
                format_func=label, key=f"{wkey}|assistant",
            )
        picks[i] = (sid, aid)

    st.markdown("---")
    b1, b2 = st.columns([1, 1])
    if b1.button("💾 Save schedule", type="primary", width="stretch"):
        errors, warnings = [], []
        usage = {}
        for i, (sid, aid) in picks.items():
            if sid is not None and sid == aid:
                errors.append(f"{names[sid]} is both student and assistant on "
                              f"'{slot_label(slots[i])}'.")
            for pid in (sid, aid):
                if pid is not None:
                    usage.setdefault(pid, []).append(slot_label(slots[i]))
            if sid and aid and categories.get(sid) != categories.get(aid):
                warnings.append(f"'{slot_label(slots[i])}': student and assistant "
                                "are in different categories.")
        for pid, parts in usage.items():
            if len(parts) > 1:
                warnings.append(f"{names[pid]} has {len(parts)} parts: {', '.join(parts)}.")
        other_type = WEEKEND if meeting_type == MIDWEEK else MIDWEEK
        _, other_picks = load_schedule(meeting_date, other_type, schedules_df)
        other_people = {p for pair in other_picks.values() for p in pair if p}
        for pid in set(usage) & other_people:
            warnings.append(f"{names[pid]} also has a part in the {other_type} on this date.")

        if errors:
            for e in errors:
                st.error(f"⚠️ {e}")
        else:
            save_schedule(meeting_date, meeting_type, slots, picks, meta_in, names)
            st.success(f"Saved {meeting_type} for {fmt_date(meeting_date)}.")
            for w in warnings:
                st.warning(f"Check: {w}")

    if saved_slots and b2.button("🗑️ Delete this schedule", width="stretch"):
        st.session_state["confirm_delete"] = (meeting_date, meeting_type)
    if st.session_state.get("confirm_delete") == (meeting_date, meeting_type):
        st.error(f"Delete the {meeting_type} for {fmt_date(meeting_date)}?")
        y, n = st.columns(2)
        if y.button("Yes, delete", type="primary"):
            delete_schedule(meeting_date, meeting_type)
            st.session_state.pop("confirm_delete")
            st.rerun()
        if n.button("Cancel"):
            st.session_state.pop("confirm_delete")
            st.rerun()

# -----------------------------------------------------------------------------
elif menu == "View Schedules":
    st.header("📋 Saved Schedules")
    schedules_df = get_schedules()
    meetings = saved_meetings(schedules_df)
    if not meetings:
        st.info("No schedules have been created yet.")
        st.stop()

    selected = st.selectbox("Meeting", meetings, format_func=meeting_label)
    meeting_date, meeting_type = selected
    rows = schedules_df[(schedules_df["meeting_date"] == meeting_date)
                        & (schedules_df["meeting_type"] == meeting_type)]
    meta = get_meeting_meta(meeting_date, meeting_type)
    if meta.get("heading"):
        st.caption(meta["heading"])

    table = pd.DataFrame({
        "Part": [slot_label(make_slot(r.part_name, r.role or "", r.section,
                                      int(r.part_no) if pd.notna(r.part_no) else None,
                                      int(r.minutes) if pd.notna(r.minutes) else None,
                                      r.hall))
                 for r in rows.itertuples()],
        "Assigned to": rows["person"].fillna("— unassigned —").tolist(),
        "Assistant": [
            (r.assistant or "— needed —") if r.needs_assistant == 1 else ""
            for r in rows.itertuples()
        ],
    })
    st.dataframe(table, width="stretch", hide_index=True)
    if st.button("✏️ Edit this schedule"):
        go("Schedule", schedule_mode="Edit saved", edit_meeting=selected)

    st.divider()
    st.subheader("🧾 S-89 assignment slips")
    student_rows = rows[(rows["student_part"] == 1) & rows["person"].notna()]
    if student_rows.empty:
        st.info("No student parts are assigned for this meeting, so there are no slips to print.")
    else:
        slip_rows = [
            {"person": r.person, "assistant": r.assistant,
             "part_no": int(r.part_no) if pd.notna(r.part_no) else None,
             "part_name": r.part_name, "meeting_date": meeting_date, "hall": r.hall}
            for r in student_rows.sort_values(["hall", "sort_order"]).itertuples()
        ]
        n_aux = sum(1 for r in slip_rows if r["hall"] == AUX_HALL)
        if n_aux:
            st.caption(f"{len(slip_rows) - n_aux} main hall and {n_aux} auxiliary "
                       "classroom slip(s); each has its room ticked.")
        st.download_button(
            f"📄 Download {len(slip_rows)} slip(s) ({selected_lang})",
            data=generate_slips_pdf(slip_rows, t),
            file_name=f"S89_slips_{meeting_date}_{selected_lang}.pdf",
            mime="application/pdf",
        )

    st.divider()
    st.subheader("🖨️ Printable schedule")
    chosen = st.multiselect("Meetings to include", meetings, default=[selected],
                            format_func=meeting_label)
    if chosen:
        chosen = sorted(chosen)
        st.download_button(
            "📄 Download schedule PDF",
            data=generate_schedule_pdf(chosen, schedules_df),
            file_name=f"schedule_{chosen[0][0]}_to_{chosen[-1][0]}.pdf",
            mime="application/pdf",
        )

# -----------------------------------------------------------------------------
elif menu == "Upload PDF Brochure":
    st.header("📖 Import Meeting Workbook (PDF)")
    st.write(
        "Upload the Life and Ministry Meeting Workbook PDF. Numbered parts with "
        "their minutes are read for each week, and you can correct them below."
    )
    uploaded_pdf = st.file_uploader("Choose PDF file", type=["pdf"])

    if uploaded_pdf is not None:
        weeks, empty, raw_text = parse_brochure(uploaded_pdf.getvalue())
        file_id = f"{uploaded_pdf.name}:{uploaded_pdf.size}"
        if st.session_state.get("brochure_file") != file_id:
            st.session_state["brochure_file"] = file_id
            st.session_state["brochure_weeks"] = weeks

        if not weeks:
            st.error(
                "No numbered parts with durations were found. The PDF may be scanned, "
                "or laid out differently. Schedules will use the standard part list."
            )
        else:
            st.success(f"Found parts for {len(weeks)} week(s).")
            if empty:
                st.warning("No parts found under: " + ", ".join(empty))
            if not any(WEEK_RE.search(w) for w in weeks):
                st.info("No English week headings were found, so weeks are listed by page. "
                        "Section guesses are based on part numbers and durations; "
                        "check them below.")

            stored = st.session_state["brochure_weeks"]
            week = st.selectbox("Review week", list(stored))
            editor_df = pd.DataFrame(stored[week]["parts"])[
                ["part_no", "title", "minutes", "section", "role"]]
            edited = st.data_editor(
                editor_df, key=f"editor|{file_id}|{week}", width="stretch",
                hide_index=True, num_rows="dynamic",
                column_config={
                    "part_no": st.column_config.NumberColumn("No.", min_value=1, step=1),
                    "title": st.column_config.TextColumn("Title", required=True),
                    "minutes": st.column_config.NumberColumn("Min", min_value=1, step=1),
                    "section": st.column_config.SelectboxColumn(
                        "Section", options=["Treasures", "Ministry", "Living"], required=True),
                    "role": st.column_config.SelectboxColumn(
                        "Role", options=ROLES, required=True),
                },
            )
            if st.button("Save corrections for this week"):
                clean = edited.dropna(subset=["title", "section", "role"])
                stored[week]["parts"] = sorted(
                    (make_slot(r.title, r.role, r.section,
                               int(r.part_no) if pd.notna(r.part_no) else None,
                               int(r.minutes) if pd.notna(r.minutes) else None)
                     for r in clean.itertuples()),
                    key=lambda p: p["part_no"] or 99,
                )
                st.success("Saved. Use 'Create Schedule' to assign this week.")

        with st.expander("View extracted raw text"):
            st.text_area("Raw text", raw_text, height=350)

# -----------------------------------------------------------------------------
elif menu == "Export":
    st.header("📤 Export")
    schedules_df = get_schedules()
    if schedules_df.empty:
        st.info("No schedule data to export yet.")
        st.stop()

    st.subheader("CSV")
    csv_df = schedules_df[["meeting_date", "meeting_type", "part_no", "part_name",
                           "minutes", "section", "role", "hall", "person", "assistant"]]
    st.download_button(
        "Download all schedules as CSV",
        data=csv_df.to_csv(index=False).encode("utf-8-sig"),  # BOM keeps ɛ/ɔ right in Excel
        file_name="meeting_schedule.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("S-140 (Word)")
    midweek = [m for m in saved_meetings(schedules_df) if m[1] == MIDWEEK]
    if not midweek:
        st.info("Save at least one midweek schedule first.")
        st.stop()
    months = sorted({m[0][:7] for m in midweek}, reverse=True)
    month = st.selectbox(
        "Month", months,
        format_func=lambda ym: datetime.strptime(ym, "%Y-%m").strftime("%B %Y"))
    month_meetings = sorted(m for m in midweek if m[0].startswith(month))
    st.caption("Weeks: " + ", ".join(fmt_date(m[0]) for m in month_meetings))

    c1, c2 = st.columns(2)
    congregation = c1.text_input("Congregation name", get_setting("congregation"))
    group_label = c2.text_input(
        "Group label", get_setting("group_label", "GROUP"),
        help="Only used for weeks without the auxiliary classroom.")
    template = st.file_uploader("Blank S-140 template (.docx)", type=["docx"])
    widen = st.checkbox("Widen title and name columns", value=True)

    data, skipped = build_s140_data(month_meetings, schedules_df, congregation, group_label)
    if skipped:
        st.warning("Skipped (need 3 Treasures parts and a Bible Study): "
                   + ", ".join(fmt_date(d) for d in skipped))

    col_a, col_b = st.columns(2)
    col_b.download_button(
        "Download data.json", data=json.dumps(data, ensure_ascii=False, indent=2),
        file_name="data.json", mime="application/json", width="stretch",
    )
    if template is not None and data["weeks"]:
        set_setting("congregation", congregation)
        set_setting("group_label", group_label)
        try:
            docx_bytes = fill_s140(template.getvalue(), data, widen=widen)
        except (S140Error, KeyError, IndexError) as exc:
            st.error(f"Couldn't fill the template: {exc}")
        else:
            month_name = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
            col_a.download_button(
                f"📄 Download {month_name}.docx", data=docx_bytes,
                file_name=f"{month_name}.docx", width="stretch",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
