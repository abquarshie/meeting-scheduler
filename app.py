# -*- coding: utf-8 -*-
"""Meeting Scheduler: midweek/weekend assignments, S-89 slips and S-140 export."""

import streamlit as st
from auth import current_user_role, can_manage_midweek, can_manage_weekend, ROLE_OVERSEER


st.set_page_config(page_title="Meeting Scheduler", page_icon=":material/event_note:",
                   layout="wide")

# If an upload went wrong, say exactly which files are missing instead of crashing.
from pathlib import Path  # noqa: E402
import shutil  # noqa: E402

# Streamlit only reads the theme from .streamlit/config.toml. When the repo keeps
# config.toml next to app.py, copy it into place (used from the next reboot).
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
        st.markdown("These files are missing from the repository "
                    "(they all belong next to `app.py`):")
        st.code("\n".join(missing), language=None)
    else:
        st.markdown(f"All app files are present, so **{exc.name}** is a package that "
                    "isn't installed. Check that `requirements.txt` lists it and "
                    "reboot the app.")
    found = sorted(
        str(f.relative_to(here)) for f in here.rglob("*")
        if f.is_file() and ".git" not in f.parts and "__pycache__" not in f.parts
    )
    with st.expander("Files the app can see"):
        st.code("\n".join(found), language=None)
    st.stop()

# --- sign-in --------------------------------------------------------------
inject_css()
try:
    ensure_db()
except Exception as exc:
    st.error(f"The app can't reach its database: {exc}")
    st.caption(
        "Check the `[database] url` in Settings → Secrets: the host, the "
        "password, and `?sslmode=require` at the end. The app needs a working "
        "database before any page will load."
    )
    st.stop()
require_login()
FONT_REGULAR, FONT_BOLD, FONT_SUPPORTS_GA = register_fonts()

if "menu" not in st.session_state:
    st.session_state["menu"] = "Dashboard"

# --- sidebar -------------------------------------------------------------------
menu = st.session_state["menu"]
sidebar(menu)

# Settings are kept together on the Admin page; the sidebar holds the one
# control that is changed while working, and a way out of a stuck form.
st.session_state.setdefault("slip_lang",
                            get_setting("slip_language", list(TRANSLATIONS)[0]))
aux_default = get_setting("use_aux", "1") == "1"
with st.sidebar.expander(tr("settings"), icon=":material/settings:"):
    st.selectbox(tr("slip_language"), list(TRANSLATIONS), key="slip_lang")
    st.caption("Congregation name, meeting days and the rest are on the Admin page.")
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
if selected_lang != "English" and not FONT_SUPPORTS_GA:
    st.sidebar.warning(
        "No font with ɛ, ɔ and ŋ was found, so Ga slips will show boxes. "
        "Put DejaVuSans.ttf and DejaVuSans-Bold.ttf next to app.py."
    )

kind, text = status_text()
icons = {"warning": ":material/cloud_off:", "error": ":material/sync_problem:",
         "info": ":material/cloud:", "success": ":material/cloud_done:"}
st.sidebar.caption(f"{icons[kind]} {text}")
logout_button()

# --- page ------------------------------------------------------------------------
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

# Role-based guard for restricted pages
user_role = current_user_role()
if menu == "Upload PDF Brochure" and user_role != "Admin" and not can_manage_midweek():
    st.warning("Access restricted: Uploading PDF Brochures is restricted to the Life and Ministry Overseer.")
    menu = "Dashboard"
    st.session_state["menu"] = menu

students_df = get_students()
PAGES.get(menu, dashboard.render)(students_df, t, selected_lang, aux_default)
