# -*- coding: utf-8 -*-
"""Look and feel: theme CSS, sidebar navigation and role-based page filtering.

Colour carries meaning only: the three workbook section colours mark sections,
and the ink blue marks actions. Everything else stays neutral.
"""
from html import escape as html_escape
from i18n import *  # noqa: F401,F403
from auth import current_user_role, ROLE_OVERSEER, ROLE_COORDINATOR

# Full navigation list with role restrictions
NAV = [
    ("Dashboard", "nav_home", ":material/space_dashboard:", "all"),
    ("Month", "nav_month", ":material/calendar_month:", "all"),
    ("Schedule", "nav_schedule", ":material/edit_calendar:", "all"),
    ("View Schedules", "nav_view", ":material/print:", "all"),
    ("Manage Participants", "nav_participants", ":material/group:", "all"),
    ("Upload PDF Brochure", "nav_workbook", ":material/menu_book:", ROLE_OVERSEER),
    ("Reports", "nav_reports", ":material/bar_chart:", "all"),
    ("Admin", "nav_admin", ":material/admin_panel_settings:", "all"),
]

CSS = """
<style>
h1, h2, h3, h4 { letter-spacing: -0.01em; }
.block-container { padding-top: 2.2rem; max-width: 1180px; }
.ms-brand { font-weight: 700; font-size: 1.05rem; margin: 0 0 .1rem 0; }
.ms-brand-sub { font-size: .8rem; opacity: .65; margin: 0 0 1rem 0; }
[class*="st-key-nav_"] button {
    justify-content: flex-start;
    padding-left: .75rem;
    border-radius: .45rem;
}
[class*="st-key-nav_"] button > div,
[class*="st-key-nav_"] button [data-testid="stMarkdownContainer"] {
    justify-content: flex-start;
    text-align: left;
    width: 100%;
}
[class*="st-key-nav_"] button p { font-weight: 500; }
[class*="st-key-nav_"] { margin-bottom: -0.55rem; }
.ms-page-title { font-size: 1.75rem; font-weight: 700; margin: 0; line-height: 1.2; }
.ms-page-sub { opacity: .7; margin: .3rem 0 1.2rem 0; max-width: 62ch; }
.ms-section { display: flex; align-items: center; gap: .6rem; margin: 1.4rem 0 .4rem 0;
              font-weight: 600; font-size: 1.05rem; }
.ms-section::before { content: ""; width: .35rem; height: 1.3rem; border-radius: 2px;
                      background: var(--ms-color); }
button:focus-visible { outline: 2px solid #24527A; outline-offset: 2px; }
</style>
"""

def go(page, **state):
    st.session_state["menu"] = page
    for key, value in state.items():
        st.session_state[key] = value
    st.rerun()

def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)

def sidebar(current):
    role = current_user_role()
    with st.sidebar:
        st.markdown(f'<div class="ms-brand">{html_escape(tr("app_name"))}</div>'
                    f'<div class="ms-brand-sub">Role: <b>{html_escape(role)}</b></div>',
                    unsafe_allow_html=True)
        for page, key, icon, allowed_role in NAV:
            if allowed_role != "all" and role != "Admin" and role != allowed_role:
                continue
            active = page == current
            if st.button(tr(key), icon=icon, key=f"nav_{page.replace(' ', '_')}",
                         type="primary" if active else "tertiary", width="stretch"):
                if not active:
                    state = {"schedule_mode": "Create new"} if page == "Schedule" else {}
                    go(page, **state)
        st.divider()

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
