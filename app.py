# -*- coding: utf-8 -*-
"""Meeting Scheduler: midweek/weekend assignments, S-89 slips and S-140 export."""

import streamlit as st


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

from scheduler.core import *  # noqa: E402,F401,F403
from scheduler.pages import (  # noqa: E402
    admin, dashboard, export, month, participants, reports, schedule, view, workbook_page,
)

# --- sign-in, then bring data back if the server started fresh --------------
init_db()
require_login()
restored = restore_if_fresh()
if restored == "restored":
    st.toast("Data loaded from Google Sheets.", icon="☁️")
elif restored:
    st.error(restored)
FONT_REGULAR, FONT_BOLD, FONT_SUPPORTS_GA = register_fonts()

if "menu" not in st.session_state:
    st.session_state["menu"] = "Dashboard"

# --- sidebar -------------------------------------------------------------------
if st.sidebar.button(tr("back"), width="stretch"):
    go("Dashboard")

selected_lang = st.sidebar.selectbox(tr("slip_language"), list(TRANSLATIONS))
t = TRANSLATIONS[selected_lang]
if selected_lang != "English" and not FONT_SUPPORTS_GA:
    st.sidebar.warning(
        "No font with ɛ, ɔ and ŋ was found, so Ga slips will show boxes. "
        "Put DejaVuSans.ttf and DejaVuSans-Bold.ttf in a 'fonts' folder next to app.py."
    )

with st.sidebar.expander(tr("settings")):
    st.selectbox(tr("ui_language"), UI_LANGUAGES, key="ui_lang")
    aux_setting = get_setting("use_aux", "1") == "1"
    aux_default = st.toggle(
        "Auxiliary classroom in use", value=aux_setting,
        help="Default for new midweek schedules. Any single week can still be switched off.",
    )
    if aux_default != aux_setting:
        set_setting("use_aux", "1" if aux_default else "0")
    ga_setting = get_setting("ga_convert", "0") == "1"
    ga_on = st.toggle(
        "Convert 3 ) N to ɛ ɔ ŋ when saving names", value=ga_setting,
        help="Turn off if a name genuinely contains 3, ) or a capital N mid-word.",
    )
    if ga_on != ga_setting:
        set_setting("ga_convert", "1" if ga_on else "0")

kind, text = status_text()
if kind != "success":
    getattr(st.sidebar, kind)(text)
else:
    st.sidebar.caption(text)
logout_button()

# --- page ------------------------------------------------------------------------
PAGES = {
    "Dashboard": dashboard.render,
    "Manage Participants": participants.render,
    "Schedule": schedule.render,
    "View Schedules": view.render,
    "Upload PDF Brochure": workbook_page.render,
    "Export": export.render,
    "Month": month.render,
    "Reports": reports.render,
    "Admin": admin.render,
}
menu = st.session_state["menu"]
students_df = get_students()
try:
    PAGES.get(menu, dashboard.render)(students_df, t, selected_lang, aux_default)
finally:
    # runs even when a page stops or reruns, so every change reaches the sheet
    sync_if_dirty()
