# -*- coding: utf-8 -*-
"""Interface wording. English is built in; Ga wording is typed in on the Admin page."""
from auth import *  # noqa: F401,F403

UI_TEXT = {
    "app_title": "📅 Meeting Scheduler",
    "app_intro": "Manage assignments and participants, and print slips and schedules.",
    "nav_view": "📋 View Schedules & Slips",
    "nav_create": "📝 Create Schedule",
    "nav_modify": "✏️ Modify Schedule",
    "nav_month": "🗓️ Month Overview",
    "nav_workbook": "📖 Upload Workbook PDF",
    "nav_participants": "👥 Manage Participants",
    "nav_reports": "📊 Reports",
    "nav_export": "📤 Export (CSV / S-140)",
    "nav_admin": "🛡️ Admin (backup, sync, log)",
    "back": "🏠 Back to Dashboard",
    "h_participants": "👥 Participants",
    "h_schedule": "📝 Create or Edit a Schedule",
    "h_view": "📋 Saved Schedules",
    "h_workbook": "📖 Import Meeting Workbook (PDF)",
    "h_export": "📤 Export",
    "h_month": "🗓️ Month Overview",
    "h_reports": "📊 Assignment Report",
    "h_admin": "🛡️ Admin",
    "save_schedule": "💾 Save schedule",
    "suggest": "✨ Suggest",
    "slip_language": "Slip language",
    "ui_language": "Interface language",
    "settings": "⚙️ Settings",
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
