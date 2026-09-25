# -*- coding: utf-8 -*-
"""Month overview: every meeting in a month, open slots, and month-wide printing."""
import calendar

from core import *  # noqa: F401,F403

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def meeting_day(meeting_type):
    key = "midweek_day" if meeting_type == MIDWEEK else "weekend_day"
    default = "Wednesday" if meeting_type == MIDWEEK else "Sunday"
    name = get_setting(key, default)
    return WEEKDAYS.index(name) if name in WEEKDAYS else WEEKDAYS.index(default)


def render(students_df, t, selected_lang, aux_default):
    page_header(tr("h_month"), tr("sub_month"))
    schedules_df = get_schedules()
    workbook, _ = load_workbook()

    months = {d[:7] for d in schedules_df["meeting_date"]}
    months |= {w["start"][:7] for w in workbook.values() if w.get("start")}
    months.add(date.today().isoformat()[:7])
    months = sorted(months, reverse=True)
    this_month = date.today().isoformat()[:7]
    month = st.selectbox(
        "Month", months, index=months.index(this_month),
        format_func=lambda ym: datetime.strptime(ym, "%Y-%m").strftime("%B %Y"),
        key="month_view_month",
    )

    in_month = schedules_df[schedules_df["meeting_date"].str.startswith(month)]
    rows, to_create = [], []
    for md, mt in sorted(saved_meetings(in_month)):
        r = in_month[(in_month["meeting_date"] == md) & (in_month["meeting_type"] == mt)]
        meta = get_meeting_meta(md, mt)
        _filled, _needed = fill_counts(r)
        rows.append({
            "Date": fmt_date(md), "Meeting": mt,
            "Filled": round(100 * _filled / max(_needed, 1)),
            "Open slots": _needed - _filled,
            "Aux. classroom": "Yes" if (r["hall"] != MAIN_HALL).any() else "",
            "Heading": meta.get("heading") or talk_text(meta),
        })

    saved_midweek = {md for md, mt in saved_meetings(schedules_df) if mt == MIDWEEK}
    for label, w in workbook.items():
        if not w.get("start"):
            continue
        start = datetime.strptime(w["start"], "%Y-%m-%d").date()
        md = (start + timedelta(days=meeting_day(MIDWEEK))).isoformat()
        if md.startswith(month) and md not in saved_midweek and \
                not any(w["start"] <= d <= w["end"] for d in saved_midweek):
            if is_no_meeting(md):
                rows.append({"Date": fmt_date(md), "Meeting": MIDWEEK, "Filled": None,
                             "Open slots": None, "Aux. classroom": "",
                             "Heading": f"{label} · no meeting (assembly/convention)"})
                continue
            to_create.append((md, label))
            rows.append({"Date": fmt_date(md), "Meeting": MIDWEEK, "Filled": None,
                         "Open slots": None, "Aux. classroom": "",
                         "Heading": f"{label} · not created yet"})

    # assemblies/conventions that don't line up with any workbook week at all
    # (e.g. one recorded ahead of time, before that week's workbook is out)
    y_, m_ = map(int, month.split("-"))
    month_start = f"{month}-01"
    month_end = f"{month}-{calendar.monthrange(y_, m_)[1]:02d}"
    shown = {r["Date"] for r in rows}
    for _pid, start, end, note in get_no_meeting_periods():
        if start > month_end or end < month_start:
            continue
        label = fmt_date(start)
        if label in shown:
            continue
        span = "" if start == end else f" – {fmt_date(end)}"
        rows.append({"Date": label, "Meeting": "—", "Filled": None,
                     "Open slots": None, "Aux. classroom": "",
                     "Heading": (note or "Assembly / Convention") + span})

    if not rows:
        st.info("Nothing scheduled this month yet.")
    else:
        table = pd.DataFrame(rows)
        table["_sort"] = pd.to_datetime(table["Date"], format="%d %B %Y")
        table = table.sort_values(["_sort", "Meeting"]).drop(columns="_sort")
        st.dataframe(table, width="stretch", hide_index=True, column_config={
            "Filled": st.column_config.ProgressColumn(
                "Filled", min_value=0, max_value=100, format="%d%%"),
        })
        total_open = int(pd.to_numeric(table["Open slots"], errors="coerce").fillna(0).sum())
        if total_open:
            st.warning(f"{total_open} slot(s) still open this month.")
        elif not to_create:
            st.success("Every slot this month is filled.")

    if to_create:
        st.markdown("**Workbook weeks without a schedule**")
        if len(to_create) > 1:
            with st.container(border=True):
                st.write(f"{len(to_create)} weeks this month have no schedule. "
                         "They can be created and filled in one go, then checked "
                         "week by week — the suggestions follow the same rotation "
                         "as the Suggest button.")
                use_aux = st.checkbox("Auxiliary classroom in these weeks",
                                      value=aux_default, key="bulk_aux")
                group = ""
                if use_aux:
                    group = nfc(st.text_input("Group using the classroom",
                                              key="bulk_group", placeholder="e.g. 1"))
                if st.button(f"Create all {len(to_create)} weeks",
                             icon=":material/auto_awesome_motion:", type="primary"):
                    made = []
                    for md, label in to_create:
                        week = workbook.get(label)
                        if not week:
                            continue
                        filled, total = create_week(md, label, week, students_df,
                                                    use_aux, group)
                        made.append(f"{fmt_date(md, short=True)} ({filled}/{total})")
                    if made:
                        st.success("Created " + ", ".join(made)
                                   + ". Open each week to check it before printing.")
                        st.rerun()
                    else:
                        st.warning("Those weeks are no longer in the workbook.")
        cols = st.columns(min(len(to_create), 4))
        for i, (md, label) in enumerate(to_create):
            if cols[i % len(cols)].button(f"Create {fmt_date(md, short=True)}",
                                          icon=":material/add:",
                                          key=f"create_{md}", width="stretch"):
                go("Schedule", schedule_mode="Create new",
                   new_meeting_type=MIDWEEK,
                   new_meeting_date=datetime.strptime(md, "%Y-%m-%d").date())

        with st.expander("One of these is an assembly or convention, not a "
                         "meeting to create?"):
            options = [f"{fmt_date(md, short=True)} — {label}" for md, label in to_create]
            picked = st.multiselect("Mark as no meeting", options,
                                    key="mark_no_meeting")
            note = st.text_input("Note", placeholder="e.g. Circuit Assembly",
                                 key="mark_no_meeting_note")
            if st.button("Mark selected", disabled=not picked):
                for p in picked:
                    md, _ = to_create[options.index(p)]
                    add_no_meeting_period(md, md, note)
                st.success(f"Marked {len(picked)} week(s). More options for the "
                          "date range are under Admin → Settings.")
                st.rerun()

    st.divider()
    if st.button("Print this month", icon=":material/print:"):
        go("View Schedules", print_scope="A whole month", print_month=month)
