# -*- coding: utf-8 -*-
"""Month overview: every meeting in a month, open slots, and month-wide printing."""
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
            to_create.append((md, label))
            rows.append({"Date": fmt_date(md), "Meeting": MIDWEEK, "Filled": None,
                         "Open slots": None, "Aux. classroom": "",
                         "Heading": f"{label} · not created yet"})

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
        cols = st.columns(min(len(to_create), 4))
        for i, (md, label) in enumerate(to_create):
            if cols[i % len(cols)].button(f"Create {fmt_date(md, short=True)}",
                                          icon=":material/add:",
                                          key=f"create_{md}", width="stretch"):
                go("Schedule", schedule_mode="Create new",
                   new_meeting_type=MIDWEEK,
                   new_meeting_date=datetime.strptime(md, "%Y-%m-%d").date())

    if in_month.empty:
        return

    st.divider()
    st.subheader("Print the whole month")
    c1, c2, c3 = st.columns(3)
    slips = slip_rows_for(in_month)
    if slips:
        c1.download_button(
            f"All {len(slips)} S-89 slips ({selected_lang})", icon=":material/receipt_long:",
            data=slips_pdf(slips, t, selected_lang),
            file_name=f"S89_slips_{month}_{selected_lang}.pdf",
            mime="application/pdf", width="stretch",
        )
    else:
        c1.info("No student parts assigned this month.")

    # the midweek and weekend sheets print separately
    month_meetings = sorted(saved_meetings(in_month))
    midweek, weekend = split_by_type(month_meetings)
    two_up = False
    if len(midweek) > 1:
        two_up = st.checkbox(
            "Two midweek weeks per sheet", value=True, key="month_two_up",
            help="A week using the auxiliary classroom still prints on its own "
                 "sheet — it is too tall to pair without shrinking it.")
    for column, picked, label in ((c2, midweek, "Midweek"), (c3, weekend, "Weekend")):
        if not picked:
            column.info(f"No {label.lower()} meeting this month.")
            continue
        column.download_button(
            f"{label} schedule ({len(picked)})", icon=":material/print:",
            data=generate_schedule_pdf(picked, schedules_df, t,
                                       compact=two_up and label == "Midweek"),
            file_name=f"{label.lower()}_schedule_{month}.pdf",
            mime="application/pdf", width="stretch", key=f"month_dl_{label}",
        )
