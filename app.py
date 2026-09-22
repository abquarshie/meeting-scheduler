# -*- coding: utf-8 -*-
"""Meeting Scheduler: midweek/weekend assignments, S-89 slips and S-140 export."""

import streamlit as st
from auth import current_user_role, is_admin, is_coordinator, ROLE_ADMIN

st.set_page_config(page_title="Meeting Scheduler", page_icon=":material/event_note:",
                   layout="wide")

from pathlib import Path  # noqa: E402
import shutil  # noqa: E402

_here = Path(__file__).resolve().parent
_theme_src, _theme_dst = _here / "config.toml", _here / ".streamlit" / "config.toml"
if _theme_src.is_file() and (not _theme_dst.exists()
                             or _theme_dst.read_bytes() != _theme_src.read_bytes()):
    try:
        (_here / ".streamlit").mkdir(exist_ok=True)
        shutil.copy(_theme_src, _theme_dst)
    except OSError:
        pass

REQUIRED_FILES = [
    "s140.py", "requirements.txt",
    "constants.py", "utils.py", "db.py", "parts.py", "workbook.py",
    "sheets_pdf.py", "slips.py",
    "picking.py", "backup.py", "auth.py", "i18n.py", "core.py",
] + [f"{p}.py" for p in (
    "admin", "dashboard", "month", "participants",
    "reports", "schedule", "view", "workbook_page")]

try:
    from core import *  # noqa: E402,F401,F403
    import admin, dashboard, month, participants  # noqa: E402
    import reports, schedule, view, workbook_page  # noqa: E402
except ModuleNotFoundError as exc:
    here = Path(__file__).resolve().parent
    missing = [f for f in REQUIRED_FILES if not (here / f).is_file()]
    st.error(f"The app can't start: Python couldn't find the module **{exc.name}**.")
    if missing:
        st.markdown("These files are missing from the repository:")
        st.code("\n".join(missing), language=None)
    st.stop()

# --- sign-in --------------------------------------------------------------
inject_css()
try:
    ensure_db()
except Exception as exc:
    st.error(f"The app can't reach its database: {exc}")
    st.stop()
require_login()

FONT_REGULAR, FONT_BOLD, FONT_SUPPORTS_GA = register_fonts()

if "menu" not in st.session_state:
    st.session_state["menu"] = "Dashboard"

# --- sidebar -------------------------------------------------------------------
menu = st.session_state["menu"]

# Security check: If a Talk Coordinator attempts to access admin-only pages, redirect them
if is_coordinator() and menu not in ("Dashboard", "Month", "Schedule", "View Schedules"):
    st.session_state["menu"] = "Dashboard"
    menu = "Dashboard"

sidebar(menu)

st.session_state.setdefault("slip_lang",
                            get_setting("slip_language", list(TRANSLATIONS)[0]))
aux_default = get_setting("use_aux", "1") == "1"

with st.sidebar.expander(tr("settings"), icon=":material/settings:"):
    st.selectbox(tr("slip_language"), list(TRANSLATIONS), key="slip_lang")
    if st.button("Clear filters and unsaved picks", icon=":material/restart_alt:",
                 type="tertiary"):
        keep = {k: st.session_state[k]
                for k in ("auth_ok", "user_name", "user_role", "slip_lang", "menu")
                if k in st.session_state}
        st.session_state.clear()
        st.session_state.update(keep)
        st.rerun()

selected_lang = st.session_state.get("slip_lang") or list(TRANSLATIONS)[0]
t = TRANSLATIONS[selected_lang]

kind, text = status_text()
icons = {"warning": ":material/cloud_off:", "error": ":material/sync_problem:",
         "info": ":material/cloud:", "success": ":material/cloud_done:"}
st.sidebar.caption(f"{icons[kind]} {text}")
logout_button()

# --- page rendering --------------------------------------------------------------
PAGES = {
    "Dashboard": dashboard.render,
    "Manage Participants": participants.render,
    "Schedule": schedule.render,
    "View Schedules": view.render,
    "Upload PDF Brochure": workbook_page.render,
    "Month": month.render,
    "Reports": reports.render,
    "Admin": admin.render,
}
students_df = get_students()
PAGES.get(menu, dashboard.render)(students_df, t, selected_lang, aux_default)
