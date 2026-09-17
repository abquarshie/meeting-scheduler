# -*- coding: utf-8 -*-
"""Home: the next meeting and what's still open, then what's coming up."""
from core import *  # noqa: F401,F403
from month import meeting_day


def greeting():
    hour = datetime.now().hour
    word = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
    name = st.session_state.get("user_name")
    return f"{word}, {name}" if name else word


def long_date(iso):
    d = datetime.strptime(iso, "%Y-%m-%d").date()
    return f"{d:%A} {d.day} {d:%B}"


def days_away(iso):
    n = (datetime.strptime(iso, "%Y-%m-%d").date() - date.today()).days
    return "today" if n == 0 else "tomorrow" if n == 1 else f"in {n} days"


def unscheduled_weeks(schedules_df, within_days=None):
    """Workbook weeks whose midweek meeting is still ahead and has no schedule.

    The meeting day is what matters, not the week: on a Thursday, the current
    week's Wednesday meeting has already happened and must not be offered.
    """
    workbook, _ = load_workbook()
    saved = {d for d, t_ in saved_meetings(schedules_df) if t_ == MIDWEEK}
    today = date.today()
    cutoff = today + timedelta(days=within_days) if within_days else None
    out = []
    for label, w in workbook.items():
        if not w.get("start"):
            continue
        if any(w["start"] <= d <= w["end"] for d in saved):
            continue
        start = datetime.strptime(w["start"], "%Y-%m-%d").date()
        meeting = start + timedelta(days=meeting_day(MIDWEEK))
        if meeting < today or (cutoff and meeting > cutoff):
            continue
        out.append((label, meeting))
    return sorted(out, key=lambda pair: pair[1])


def next_unscheduled_week(schedules_df):
    weeks = unscheduled_weeks(schedules_df)
    return weeks[0] if weeks else None


def render(students_df, t, selected_lang, aux_default):
    today = date.today()
    page_header(greeting(), f"{today:%A} {today.day} {today:%B %Y}")

    if students_df.empty:
        with st.container(border=True):
            st.markdown("### Add your participants first")
            st.write("Schedules are filled from the people you add, with the parts "
                     "each one can take.")
            if st.button("Add participants", icon=":material/person_add:", type="primary"):
                go("Manage Participants")
        return

    schedules_df = get_schedules()
    upcoming = sorted(p for p in saved_meetings(schedules_df) if p[0] >= today.isoformat())
    gap = next_unscheduled_week(schedules_df)

    # ---- the next meeting -----------------------------------------------------
    with st.container(border=True):
        if upcoming:
            md, mt = upcoming[0]
            rows = schedules_df[(schedules_df["meeting_date"] == md)
                                & (schedules_df["meeting_type"] == mt)]
            meta = get_meeting_meta(md, mt)
            filled, needed = fill_counts(rows)
            open_n = needed - filled
            detail = meta.get("heading") if mt == MIDWEEK else talk_text(meta)
            sub = f"{mt.capitalize()}, {days_away(md)}" + (f". {detail}" if detail else "")
            left, right = st.columns([3, 1], gap="large")
            with left:
                st.markdown(f'<div class="ms-next-when">{long_date(md)}</div>'
                            f'<div class="ms-next-meta">{html_escape(sub)}</div>',
                            unsafe_allow_html=True)
                section_bars(rows)
            with right:
                word = "slot open" if open_n == 1 else "slots open"
                st.markdown(
                    f'<div class="ms-open">{open_n}</div>'
                    f'<div class="ms-open-label">{word if open_n else "Every part is filled"}</div>',
                    unsafe_allow_html=True)
                if st.button("Fill open slots" if open_n else "Edit schedule",
                             icon=":material/edit:", type="primary" if open_n else "secondary",
                             width="stretch", key="home_fill"):
                    go("Schedule", schedule_mode="Edit saved", edit_meeting=(md, mt))
                if st.button("Print slips", icon=":material/print:", width="stretch",
                             key="home_print"):
                    go("View Schedules", view_meeting=(md, mt))
        elif gap:
            label, when = gap
            st.markdown(f'<div class="ms-next-when">{long_date(when.isoformat())}</div>'
                        f'<div class="ms-next-meta">{html_escape(label)} has no schedule yet.</div>',
                        unsafe_allow_html=True)
            if st.button("Create this week", icon=":material/add:", type="primary",
                         key="home_gap_first"):
                go("Schedule", schedule_mode="Create new",
                   new_meeting_type=MIDWEEK, new_meeting_date=when)
        else:
            st.markdown('<div class="ms-next-when">No meetings scheduled yet</div>'
                        '<div class="ms-next-meta">Upload the workbook to get each week’s '
                        'parts, then create the first schedule.</div>',
                        unsafe_allow_html=True)
            c1, c2, _ = st.columns([1, 1, 2])
            if c1.button("Create a schedule", icon=":material/add:", type="primary",
                         width="stretch"):
                go("Schedule", schedule_mode="Create new")
            if c2.button("Upload workbook", icon=":material/upload_file:", width="stretch"):
                go("Upload PDF Brochure")

    if upcoming and gap:
        label, when = gap
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.info(f"{label} ({long_date(when.isoformat())}) has no schedule yet.",
                icon=":material/event_busy:")
        if c2.button("Create it", icon=":material/add:", width="stretch", key="home_gap"):
            go("Schedule", schedule_mode="Create new",
               new_meeting_type=MIDWEEK, new_meeting_date=when)

    # ---- at a glance --------------------------------------------------------------
    soon = [p for p in upcoming
            if p[0] <= (today + timedelta(days=28)).isoformat()]
    open_soon = 0
    for md, mt in soon:
        f_, n_ = fill_counts(schedules_df[(schedules_df["meeting_date"] == md)
                                          & (schedules_df["meeting_type"] == mt)])
        open_soon += n_ - f_
    week_end = (today + timedelta(days=6)).isoformat()
    away = set()
    d = today
    while d.isoformat() <= week_end:
        away |= get_unavailable(d.isoformat())
        d += timedelta(days=1)
    away |= get_suspended(students_df, today.isoformat())
    m1, m2, m3 = st.columns(3)
    not_created = unscheduled_weeks(schedules_df, within_days=28)
    if not soon and not_created:
        # no schedules ahead, so "0 open slots" would read as "nothing to do"
        m1.metric("Weeks not yet created", len(not_created), border=True,
                  help="Workbook weeks in the next 4 weeks with no schedule.")
    else:
        m1.metric("Open slots in the next 4 weeks", open_soon, border=True,
                  help=(f"{len(not_created)} week(s) in this period still have no "
                        "schedule." if not_created else None))
    m2.metric("Active participants", int((students_df["active"] == 1).sum()), border=True)
    m3.metric("Away or suspended this week", len(away), border=True)

    # ---- coming up ----------------------------------------------------------------
    later = upcoming[1:9]
    if later:
        st.markdown("#### Coming up")
        table = []
        for md, mt in later:
            rows = schedules_df[(schedules_df["meeting_date"] == md)
                                & (schedules_df["meeting_type"] == mt)]
            meta = get_meeting_meta(md, mt)
            f_, n_ = fill_counts(rows)
            table.append({
                "Date": datetime.strptime(md, "%Y-%m-%d").strftime("%a %d %b"),
                "Meeting": "Midweek" if mt == MIDWEEK else "Weekend",
                "Week or talk": (meta.get("heading") if mt == MIDWEEK
                                 else talk_text(meta)) or "",
                "Filled": round(100 * f_ / n_) if n_ else 100,
                "Open": n_ - f_,
                "_key": (md, mt),
            })
        df = pd.DataFrame(table)
        event = st.dataframe(
            df.drop(columns="_key"), hide_index=True, width="stretch",
            on_select="rerun", selection_mode="single-row", key="home_upcoming",
            column_config={
                "Filled": st.column_config.ProgressColumn(
                    "Filled", min_value=0, max_value=100, format="%d%%"),
                "Open": st.column_config.NumberColumn("Open", width="small"),
            },
        )
        st.caption("Select a row to open that schedule.")
        picked = getattr(getattr(event, "selection", None), "rows", None)
        if picked:
            go("Schedule", schedule_mode="Edit saved", edit_meeting=df.iloc[picked[0]]["_key"])
