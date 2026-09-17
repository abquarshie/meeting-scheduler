# -*- coding: utf-8 -*-
"""Interface wording. English is built in; Ga wording is typed in on the Admin page."""
from auth import *  # noqa: F401,F403

UI_TEXT = {
    "app_name": "Meeting Scheduler",
    "app_tagline": "Life and Ministry assignments",
    "nav_home": "Home",
    "nav_month": "Month overview",
    "nav_schedule": "Create or edit",
    "nav_view": "Slips and printing",
    "nav_participants": "Participants",
    "nav_workbook": "Workbook PDF",
    "nav_reports": "Reports",
    "nav_export": "Export",
    "nav_admin": "Admin",
    "h_participants": "Participants",
    "sub_participants": "Who can take which parts, families, away dates and suspensions.",
    "h_schedule": "Create or edit a schedule",
    "sub_schedule": "Pick a date, then fill each part. Only eligible people are listed.",
    "h_view": "Slips and printing",
    "sub_view": "S-89 slips, reminders and a printable schedule for one meeting.",
    "h_workbook": "Workbook PDF",
    "sub_workbook": "Upload the meeting workbook so each week gets its real parts.",
    "h_export": "Export",
    "sub_export": "Download the schedules as CSV, or fill your S-140 template.",
    "h_month": "Month overview",
    "sub_month": "Every meeting this month, what is still open, and month-wide printing.",
    "h_reports": "Reports",
    "sub_reports": "How often each person had a part, to spot anyone left out.",
    "h_admin": "Admin",
    "sub_admin": "Backups, Google Sheets, meeting days, wording and the change log.",
    "save_schedule": "Save schedule",
    "suggest": "Suggest",
    "slip_language": "Slip language",
    "ui_language": "Interface language",
    "settings": "Settings",
}
UI_LANGUAGES = ["English", "Ga"]


def ui_overrides(lang):
    if lang == "English":
        return {}
    try:
        return json.loads(get_setting(f"ui_text_{lang}", "{}") or "{}")
    except ValueError:
        return {}


def tr(key):
    """Interface text in the chosen language, falling back to English."""
    lang = st.session_state.get("ui_lang", "English")
    text = ui_overrides(lang).get(key)
    return text or UI_TEXT.get(key, key)


def save_ui_overrides(lang, mapping):
    clean = {k: nfc(v) for k, v in mapping.items() if k in UI_TEXT and nfc(v)}
    set_setting(f"ui_text_{lang}", json.dumps(clean, ensure_ascii=False))
    log_change("Interface wording changed", f"{lang}: {len(clean)} item(s)")
