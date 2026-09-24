# -*- coding: utf-8 -*-
"""Look and feel: theme CSS, sidebar navigation and small display pieces.

Colour carries meaning only: the three workbook section colours mark sections,
and the ink blue marks actions. Everything else stays neutral.
"""
from html import escape as html_escape

from i18n import *  # noqa: F401,F403

# page key, wording key, Material icon
NAV = [
    ("Dashboard", "nav_home", ":material/space_dashboard:"),
    ("Month", "nav_month", ":material/calendar_month:"),
    ("Schedule", "nav_schedule", ":material/edit_calendar:"),
    ("View Schedules", "nav_view", ":material/print:"),
    ("Manage Participants", "nav_participants", ":material/group:"),
    ("Upload PDF Brochure", "nav_workbook", ":material/menu_book:"),
    ("Reports", "nav_reports", ":material/bar_chart:"),
    ("Admin", "nav_admin", ":material/admin_panel_settings:"),
]

CSS = """
<style>
/* typeface comes from the theme (config.toml); only sizes and spacing here */
h1, h2, h3, h4 { letter-spacing: -0.01em; }
.block-container { padding-top: 2.2rem; max-width: 1180px; }

/* sidebar: brand + navigation list */
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


def go(page, **state):
    """Switch page, optionally presetting widget state, and rerun."""
    st.session_state["menu"] = page
    for key, value in state.items():
        st.session_state[key] = value
    st.rerun()


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def sidebar(current):
    """App name, then one row per page."""
    with st.sidebar:
        st.markdown(f'<div class="ms-brand">{html_escape(tr("app_name"))}</div>'
                    f'<div class="ms-brand-sub">{html_escape(tr("app_tagline"))}</div>',
                    unsafe_allow_html=True)
        for page, key, icon in NAV:
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
