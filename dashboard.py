# File: dashboard.py
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


def setup_gaps(students_df):
    """What a new installation still needs before it can print.

    Each of these otherwise shows up as an error at the moment someone tries
    to use it, which is the worst time to find out.
    """
    gaps = []
    if students_df.empty:
        gaps.append(("Add your participants", "Manage Participants"))
    if not get_setting("congregation"):
        gaps.append(("Set the congregation name — it heads every schedule sheet",
                     "Admin"))
    workbook, _ = load_workbook()
    if not workbook:
        gaps.append(("Upload the meeting workbook so weeks get their real parts",
                     "Upload PDF Brochure"))
    if not any(load_template(f"s89_{language}")[0] for language in TRANSLATIONS):
        gaps.append(("Upload the blank S-89 — slips are printed on it", "Admin"))
    if not any(load_template(f"s140_{language}")[0]
               for language in TRANSLATIONS):
        gaps.append(("Upload the blank S-140 template for the monthly export",
                     "Admin"))
    return gaps


def render(students_df, t, selected_lang, aux_default):
    today = date.today()
    role = current_role()
    page_header(greeting(), f"{today:%A} {today.day} {today:%B %Y}")

    gaps = setup_gaps(students_df)
    # The workbook, S-89 and S-140 all feed the midweek meeting, so a
    # Talk Coordinator has no reason to be nudged about them.
    if not may_touch(MIDWEEK, role):
        gaps = [(w, p) for w, p in gaps
                if "workbook" not in w.lower()
                and "S-89" not in w
                and "S-140" not in w]
    if gaps:
        with st.container(border=True):
            st.markdown("#### Still to set up")
            for n, (what, page) in enumerate(gaps):
                c1, c2 = st.columns([4, 1], vertical_alignment="center")
                c1.write(what)
                if c2.button("Go", key=f"setup_{n}", width="stretch"):
                    go(page)
            st.caption("This disappears as each one is done.")

    if students_df.empty:
        with st.container(border=True):
            st.markdown("### Add your participants first")
            st.write("Schedules are filled from the people you add, with the parts "
                     "each one can take.")
            if st.button("Add participants", icon=":material/person_add:", type="primary"):
                go("Manage Participants")
        return

    # Both roles read the same tables; only the role's meetings reach the page.
    schedules_df = filter_schedules(get_schedules(), role)
    upcoming = sorted(p for p in saved_meetings(schedules_df) if p[0] >= today.isoformat())
    gap = next_unscheduled_week(schedules_df) if may_touch(MIDWEEK, role) else None

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
                             icon=":material/edit:",
                             type="primary" if open_n else "secondary",
                             width="stretch", key="home_fill",
                             help="Suggest fills only the empty ones; anyone "
                                  "already chosen stays." if open_n else None):
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
            if may_touch(MIDWEEK, role) and c2.button(
                    "Upload workbook", icon=":material/upload_file:", width="stretch"):
                go("Upload PDF Brochure")

    if upcoming and gap:
        label, when = gap
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.info(f"{label} ({long_date(when.isoformat())}) has no schedule yet.",
                icon=":material/event_busy:")
        if c2.button("Create it", icon=":material/add:", width="stretch", key="home_gap"):
            go("Schedule", schedule_mode="Create new",
               new_meeting_type=MIDWEEK, new_meeting_date=when)

    # ---- is there a second copy of the data anywhere? ------------------------------
    overdue, days = backup_overdue()
    if overdue and not schedules_df.empty:
        never = days is None
        st.warning(
            ("No backup file has been downloaded yet."
             if never else f"Last backup was {days} days ago.")
            + " The database is the only copy of your schedules until you take one.",
            icon=":material/cloud_off:")
        if st.button("Back up now", icon=":material/backup:", key="home_backup"):
            go("Admin")

    # ---- at a glance --------------------------------------------------------------
    soon = [p for p in upcoming
            if p[0] <= (today + timedelta(days=28)).isoformat()]
    open_soon = 0
    for md, mt in soon:
        f_, n_ = fill_counts(schedules_df[(schedules_df["meeting_date"] == md)
                                          & (schedules_df["meeting_type"] == mt)])
        open_soon += n_ - f_
    week_end = (today + timedelta(days=6)).isoformat()
    away = get_unavailable_between(today.isoformat(), week_end)
    away |= get_suspended(students_df, today.isoformat())
    m1, m2, m3 = st.columns(3)
    not_created = (unscheduled_weeks(schedules_df, within_days=28)
                   if may_touch(MIDWEEK, role) else [])
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
