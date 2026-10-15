# -*- coding: utf-8 -*-
"""Look and feel: theme CSS, sidebar navigation and small display pieces.

Colour carries meaning only: the three workbook section colours mark sections,
and the ink blue marks actions. Everything else stays neutral.
"""
from datetime import date
from html import escape as html_escape

import streamlit as st
import streamlit.components.v1 as components

from constants import EVENT_KINDS, EVENT_NAMES, SECTION_COLORS, SECTION_TITLES
from db import event_text, fill_counts, mark_event_week, meetings_in_week
from utils import fmt_date, week_label

APP_NAME = "Meeting Scheduler"

# One name per page: the menu label, the page heading and what go() is given.
NAV_SECTIONS = {
    "Schedule": ["Home", "Month overview", "Create or edit", "Slips and printing"],
    "Congregation": ["Public talks", "Participants", "Workbook PDF"],
    "Records": ["Reports", "Admin"],
}
NAV_ICONS = {
    "Home": ":material/space_dashboard:",
    "Month overview": ":material/calendar_month:",
    "Create or edit": ":material/edit_calendar:",
    "Slips and printing": ":material/print:",
    "Public talks": ":material/record_voice_over:",
    "Participants": ":material/group:",
    "Workbook PDF": ":material/menu_book:",
    "Reports": ":material/bar_chart:",
    "Admin": ":material/admin_panel_settings:",
}
PAGE_NAMES = [name for names in NAV_SECTIONS.values() for name in names]

CSS = """
<style>
/* typeface comes from the theme (config.toml); only sizes and spacing here */
h1, h2, h3, h4 { letter-spacing: -0.01em; }
/* the toolbar overlapped the page title; give the title room below it */
.block-container { padding-top: 3.4rem; padding-bottom: 4rem; max-width: 1180px; }
[data-testid="stHeader"] { background: transparent; }
/* Streamlit's own buttons in the top bar (Share, star, edit, GitHub, Fork,
   Deploy) are for the developer, not for the congregation */
[data-testid="stToolbarActions"], [data-testid="stAppDeployButton"] { display: none; }

/* Save stays in reach on the long schedule form */
/* sticky goes on Streamlit's wrapper: the keyed box fills it exactly, so
   on the box itself sticky has no room to move */
div:has(> .st-key-savebar) { position: sticky; bottom: 0; z-index: 50; }
.st-key-savebar { padding: .75rem 1rem;
                  border-top: 1px solid rgba(128,128,128,.25);
                  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
                  background: rgba(128,128,128,.10); border-radius: .6rem .6rem 0 0; }

/* page header */
.ms-page-title { font-size: 1.75rem; font-weight: 700; margin: 0; line-height: 1.2; }
.ms-page-sub { opacity: .7; margin: .3rem 0 1.2rem 0; max-width: 62ch; }

/* next-meeting panel on the dashboard */
.ms-hero-accent { width: 2.75rem; height: 3px; border-radius: 99px;
                  background: #24527A; margin: 0 0 .9rem 0; }
.ms-next-when { font-size: 2rem; font-weight: 700; line-height: 1.15; margin: 0;
                letter-spacing: -0.01em; }
.ms-next-meta { opacity: .65; margin: .3rem 0 1.3rem 0; font-size: .95rem; }
.ms-bars { display: grid; gap: .85rem; }
.ms-bar-row { display: grid; grid-template-columns: minmax(10rem, 17rem) 1fr 4.5rem;
              align-items: center; gap: .9rem; }
.ms-bar-name { font-size: .9rem; display: flex; align-items: center; gap: .55rem; }
.ms-swatch { width: .6rem; height: .6rem; border-radius: 2px; flex: none;
             box-shadow: inset 0 0 0 1px rgba(128,128,128,.35); }
.ms-bar-track { height: .45rem; border-radius: 99px; background: rgba(128,128,128,.15);
                overflow: hidden; }
.ms-bar-fill { height: 100%; border-radius: 99px; transition: width .35s ease; }
.ms-bar-count { font-variant-numeric: tabular-nums; text-align: right; font-size: .88rem;
                opacity: .8; }
.ms-open { font-size: 3rem; font-weight: 700; line-height: 1; margin: 0;
           font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
.ms-open-label { opacity: .65; margin: .3rem 0 1rem 0; font-size: .92rem; }

/* at a glance: one strip with hairline dividers, not three repeated cards */
.ms-stats { display: flex; border: 1px solid rgba(128,128,128,.25);
            border-radius: .9rem; overflow: hidden; margin: 1.4rem 0 .5rem 0; }
.ms-stat { flex: 1; padding: .9rem 1.2rem; position: relative; }
.ms-stat + .ms-stat::before { content: ""; position: absolute; left: 0;
                              top: .9rem; bottom: .9rem; width: 1px;
                              background: rgba(128,128,128,.25); }
.ms-stat-value { font-size: 1.6rem; font-weight: 700; line-height: 1;
                 font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }
.ms-stat-label { opacity: .65; font-size: .85rem; margin-top: .35rem; }
@media (max-width: 640px) {
  /* the save bar stays two short rows on a phone instead of stacking four
     full-width blocks over the form: progress, then the buttons side by side */
  .st-key-savebar { padding: .5rem .75rem; }
  /* Streamlit Cloud draws its badge over the bottom-right corner of the
     page; keep the save bar clear of it */
  div:has(> .st-key-savebar) { bottom: 4.25rem; }
  .st-key-savebar [data-testid="stHorizontalBlock"] { flex-direction: row !important;
      flex-wrap: wrap !important; gap: .4rem !important; }
  .st-key-savebar [data-testid="stColumn"] { flex: 1 1 0 !important;
      width: auto !important; min-width: 0 !important; }
  .st-key-savebar [data-testid="stColumn"]:first-child { flex-basis: 100% !important; }
  .st-key-savebar [data-testid="stColumn"]:nth-child(2) { flex-grow: 3 !important; }
  /* Undo and Delete as their icons alone; the words don't fit */
  .st-key-savebar [data-testid="stColumn"]:nth-child(n+3) [data-testid="stMarkdownContainer"] {
      display: none; }
  .ms-bar-row { grid-template-columns: 1fr 3.5rem; }
  .ms-bar-track { grid-column: 1 / -1; grid-row: 2; }
  .ms-next-when { font-size: 1.6rem; }
  .ms-open { font-size: 2.4rem; }
  .ms-stats { flex-direction: column; }
  .ms-stat + .ms-stat::before { display: none; }
  .ms-stat + .ms-stat { border-top: 1px solid rgba(128,128,128,.25); }
}

/* section headings inside a schedule */
.ms-section { display: flex; align-items: center; gap: .6rem; margin: 1.4rem 0 .4rem 0;
              font-weight: 600; font-size: 1.05rem; }
.ms-section::before { content: ""; width: .35rem; height: 1.3rem; border-radius: 2px;
                      background: var(--ms-color);
                      box-shadow: inset 0 0 0 1px rgba(128,128,128,.3); }

button:focus-visible { outline: 2px solid #24527A; outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
"""


def flash(message, icon=":material/check_circle:"):
    """A confirmation that survives the rerun that follows a save.

    st.success() followed by st.rerun() is wiped before anyone sees it; the
    message is kept here and shown as a toast at the start of the next run.
    """
    st.session_state.setdefault("_flash", []).append((message, icon))


def show_flashes():
    for message, icon in st.session_state.pop("_flash", []):
        st.toast(message, icon=icon)


def choice(label, options, key, default, where=st, **kw):
    """A segmented control that always holds one option, like a radio."""
    if st.session_state.get(key) not in options:
        st.session_state[key] = default
    return where.segmented_control(label, options, key=key, required=True, **kw)


_CLOSE_MENU_ON_PHONES = """<script>
// On a phone the open sidebar covers the page, and Streamlit leaves it open
// after a page is chosen. Close it then. Installed once per browser tab: the
// listener sits on the app's own document (this frame shares its origin).
const doc = window.parent.document;
if (!window.parent.__msCloseMenu) {
  window.parent.__msCloseMenu = true;
  doc.addEventListener("click", (e) => {
    if (!e.target.closest('[data-testid="stSidebarNavLink"]')) return;
    if (window.parent.innerWidth >= 768) return;
    setTimeout(() => {
      const b = doc.querySelector('[data-testid="stSidebarCollapseButton"] button');
      if (b) b.click();
    }, 150);
  }, true);
}
</script>"""


def close_menu_on_phones():
    with st.sidebar:
        components.html(_CLOSE_MENU_ON_PHONES, height=0)


def lazy_tabs(labels, key):
    """Tabs that build only the open one, and keep it in the address.

    Plain st.tabs runs every tab on every rerun — on the printing page that
    meant drawing both WhatsApp cards while someone was choosing slips.
    """
    return st.tabs(labels, key=key, on_change="rerun", bind="query-params")


def go(page, **state):
    """Switch page, optionally presetting widget state, and rerun."""
    st.session_state["menu"] = page
    for key, value in state.items():
        st.session_state[key] = value
    st.rerun()


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def follow_menu(shown, pages):
    """Keep st.navigation and session_state["menu"] in step.

    Someone choosing from the menu changes the page shown; code changing
    page (go(), a test) sets "menu". Whichever changed since the last run
    wins: a menu choice is written back to "menu", a new "menu" switches
    the page.
    """
    last = st.session_state.get("_nav_shown")
    if last is not None and shown != last:            # chosen from the menu
        st.session_state["menu"] = shown
        if shown == "Create or edit":                  # as the old menu did
            st.session_state["schedule_mode"] = "Create new"
    wanted = st.session_state.get("menu")
    if wanted not in pages:                            # unset, or renamed
        wanted = shown
    st.session_state["menu"] = wanted
    st.session_state["_nav_shown"] = wanted
    # the page actually shown, for the test runner (see conftest.run): a
    # browser keeps it in the address, AppTest forgets st.switch_page
    st.session_state["_nav_hash"] = pages[wanted]._script_hash
    if wanted != shown:
        st.switch_page(pages[wanted])


def page_header(title, subtitle=None):
    html = f'<div class="ms-page-title">{html_escape(title)}</div>'
    html += f'<div class="ms-page-sub">{html_escape(subtitle)}</div>' if subtitle else \
        '<div style="height:1rem"></div>'
    st.markdown(html, unsafe_allow_html=True)


def section_heading(section):
    color = SECTION_COLORS.get(section, "#8A94A0")
    name = SECTION_TITLES.get(section, section or "")
    st.markdown(f'<div class="ms-section" style="--ms-color:{color}">'
                f'{html_escape(name)}</div>', unsafe_allow_html=True)


def section_bars(rows):
    """Filled/needed bars per workbook section for one meeting's schedule rows."""
    order = ["Treasures", "Ministry", "Living", "Weekend"]
    html = ['<div class="ms-bars">']
    for section in order:
        part = rows[rows["section"] == section]
        if part.empty:
            continue
        filled, needed = fill_counts(part)
        pct = 0 if not needed else round(100 * filled / needed)
        color = SECTION_COLORS[section]
        html.append(
            f'<div class="ms-bar-row"><div class="ms-bar-name">'
            f'<span class="ms-swatch" style="background:{color}"></span>'
            f'{html_escape(SECTION_TITLES[section])}</div>'
            f'<div class="ms-bar-track"><div class="ms-bar-fill" '
            f'style="width:{pct}%;background:{color}"></div></div>'
            f'<div class="ms-bar-count">{filled} of {needed}</div></div>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def mark_event_week_form(key, default_day=None):
    """Mark a week as a circuit assembly or convention week.

    Any day in the week will do: the whole Monday–Sunday week is marked.
    Meetings already saved that week are listed and cleared only once that
    is ticked, since marking the week removes them.
    """
    c1, c2 = st.columns(2)
    day = c1.date_input("Any day in the week", default_day or date.today(),
                        key=f"event_day|{key}")
    kind = c2.radio("Kind of week", list(EVENT_KINDS), horizontal=True,
                    format_func=EVENT_NAMES.get, key=f"event_kind|{key}")
    st.caption(f"**{week_label(day)}** will show **{event_text(kind)}** "
               f"(in Ga: {event_text(kind, 'Ga')})")
    saved = meetings_in_week(day)
    sure = True
    if saved:
        st.warning(
            "Already saved that week: "
            + ", ".join(f"{t.split()[0].lower()} {fmt_date(d, short=True)}"
                        for d, t in saved)
            + ". Marking the week clears them.", icon=":material/warning:")
        sure = st.checkbox("Clear them (to bring one back later, remove the mark, "
                           "then use Undo on Create or edit)",
                           key=f"event_sure|{key}")
    if st.button(f"Mark as {EVENT_NAMES[kind]} week", type="primary",
                 disabled=not sure, key=f"event_go|{key}"):
        mark_event_week(day, kind)
        st.rerun()
