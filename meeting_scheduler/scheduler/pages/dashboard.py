# -*- coding: utf-8 -*-
"""Dashboard page."""
from scheduler.core import *  # noqa: F401,F403


def render(students_df, t, selected_lang, aux_default):
    st.title(tr("app_title"))
    st.write(tr("app_intro"))
    st.markdown("---")

    c1, c2, c3 = st.columns(3)
    if c1.button(tr("nav_view"), width="stretch"):
        go("View Schedules")
    if c2.button(tr("nav_create"), width="stretch"):
        go("Schedule", schedule_mode="Create new")
    if c3.button(tr("nav_modify"), width="stretch"):
        go("Schedule", schedule_mode="Edit saved")

    c4, c5, c6 = st.columns(3)
    if c4.button(tr("nav_month"), width="stretch"):
        go("Month")
    if c5.button(tr("nav_workbook"), width="stretch"):
        go("Upload PDF Brochure")
    if c6.button(tr("nav_participants"), width="stretch"):
        go("Manage Participants")

    c7, c8, c9 = st.columns(3)
    if c7.button(tr("nav_reports"), width="stretch"):
        go("Reports")
    if c8.button(tr("nav_export"), width="stretch"):
        go("Export")
    if c9.button(tr("nav_admin"), width="stretch"):
        go("Admin")

    if st.button("🔄 Reset session (clears filters and unsaved picks)"):
        keep = {k: st.session_state[k] for k in ("auth_ok", "user_name", "ui_lang")
                if k in st.session_state}
        st.session_state.clear()
        st.session_state.update(keep)
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
