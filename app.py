# -*- coding: utf-8 -*-
"""Meeting Scheduler: midweek/weekend assignments, S-89 slips and S-140 export."""

import streamlit as st


st.set_page_config(page_title="Meeting Scheduler", page_icon=":material/event_note:",
                   layout="wide")

# If an upload went wrong, say exactly which files are missing instead of crashing.
from pathlib import Path  # noqa: E402

# The theme lives in .streamlit/config.toml, which Streamlit reads at start-up.
# (Copying a config.toml into place from here never worked on Streamlit Cloud:
# every boot is a fresh copy of the repo, so the copy always came too late.)

REQUIRED_FILES = [
    "s140.py", "requirements.txt", "card_image.py",
    "constants.py", "utils.py", "db.py", "parts.py", "workbook.py",
    "sheets_pdf.py", "slips.py",
    "picking.py", "backup.py", "auth.py", "ui.py",
] + [f"{p}.py" for p in (
    "admin", "dashboard", "month", "participants",
    "reports", "schedule", "talks", "view", "workbook_page")]

try:
    from constants import TRANSLATIONS  # noqa: E402
    from db import (ensure_db, get_setting, get_students,  # noqa: E402
                    set_setting, status_text)
    from sheets_pdf import register_fonts  # noqa: E402
    from auth import logout_button, require_login  # noqa: E402
    from ui import (NAV_ICONS, NAV_SECTIONS, close_menu_on_phones,  # noqa: E402
                    follow_menu, inject_css, show_flashes)
    import admin, dashboard, month, participants  # noqa: E402
    import reports, schedule, talks, view, workbook_page  # noqa: E402
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
except ImportError as exc:
    # the file is there but is an older version that lacks a name the rest of
    # the app now needs — usually one file missed in an upload, or the app
    # still holding the old copy in memory
    st.error(f"The app can't start: **{exc.name}.py** is out of date.")
    st.markdown(
        f"Python found `{exc.name}.py` but not everything the other files expect "
        f"in it ({exc}).\n\n"
        f"1. On GitHub, check that `{exc.name}.py` is the latest version and "
        "upload it again if not.\n"
        "2. Then click **Manage app** (lower right) → **⋮ → Reboot app**, so "
        "the app stops using the copy it loaded earlier.")
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

# --- pages ---------------------------------------------------------------------
# Streamlit's own navigation: each page has its address (…/create-or-edit),
# refresh and the back button work, and on a phone the sidebar closes after
# a page is chosen. "menu" in session state stays the way code changes page
# (go() and the tests set it), so the two are kept in step below.
RENDER = {
    "Home": dashboard.render,
    "Month overview": month.render,
    "Create or edit": schedule.render,
    "Slips and printing": view.render,
    "Public talks": talks.render,
    "Participants": participants.render,
    "Workbook PDF": workbook_page.render,
    "Reports": reports.render,
    "Admin": admin.render,
}


def _page(name):
    def run():
        RENDER[name](get_students(), t, selected_lang, aux_default)
    slug = name.lower().replace(" ", "-")
    return st.Page(run, title=name, icon=NAV_ICONS[name], url_path=slug,
                   default=name == "Home")


PAGES = {name: _page(name) for name in RENDER}
current = st.navigation({section: [PAGES[n] for n in names]
                         for section, names in NAV_SECTIONS.items()})
follow_menu(current.title, PAGES)

# Settings are kept together on the Admin page; the sidebar holds the one
# control that is changed while working, and a way out of a stuck form.
# The language lives only here: a change is saved at once and becomes the
# default the next time anyone opens the app.
if st.session_state.get("slip_lang") not in TRANSLATIONS:
    saved_lang = get_setting("slip_language", "")
    st.session_state["slip_lang"] = (saved_lang if saved_lang in TRANSLATIONS
                                     else list(TRANSLATIONS)[0])


def _remember_language():
    set_setting("slip_language", st.session_state["slip_lang"])


aux_default = get_setting("use_aux", "1") == "1"
with st.sidebar.expander("Settings", icon=":material/settings:"):
    st.selectbox("Slip language", list(TRANSLATIONS), key="slip_lang",
                 on_change=_remember_language,
                 help="For slips, schedule sheets and the S-140. Saved as the "
                      "default for next time.")
    st.caption("Congregation name, meeting days and the rest are on the Admin page.")
    if st.button("Clear filters and unsaved picks", icon=":material/restart_alt:",
                 type="tertiary"):
        keep = {k: st.session_state[k]
                for k in ("auth_ok", "user_name", "slip_lang", "menu", "_nav_shown")
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
icons = {"error": ":material/sync_problem:", "success": ":material/cloud_done:"}
st.sidebar.caption(f"{icons[kind]} {text}")
logout_button()

show_flashes()
close_menu_on_phones()

# --- page ------------------------------------------------------------------------
current.run()
