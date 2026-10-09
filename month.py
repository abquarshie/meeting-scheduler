# -*- coding: utf-8 -*-
"""Month overview: every meeting in a month, open slots, and month-wide printing."""
import calendar
from datetime import date, datetime

import pandas as pd
import streamlit as st

from constants import MAIN_HALL, MIDWEEK
from db import (
    meeting_rows,
    event_label,
    event_text,
    fill_counts,
    get_meeting_meta,
    get_no_meeting_periods,
    get_schedules,
    saved_meetings,
    talk_text,
)
from picking import create_week
from ui import flash, go, mark_event_week_form, page_header
from utils import month_label, fmt_date, nfc
from workbook import load_workbook, midweek_workbook_weeks


def render(students_df, t, selected_lang, aux_default):
    page_header("Month overview",
                "Every meeting this month, what is still open, and month-wide printing.")
    schedules_df = get_schedules()
    workbook, _ = load_workbook()

    months = {d[:7] for d in schedules_df["meeting_date"]}
    months |= {w["start"][:7] for w in workbook.values() if w.get("start")}
    months.add(date.today().isoformat()[:7])
    months = sorted(months, reverse=True)
    this_month = date.today().isoformat()[:7]
    month = st.selectbox(
        "Month", months, index=months.index(this_month),
        format_func=month_label,
        key="month_view_month",
    )

    in_month = schedules_df[schedules_df["meeting_date"].str.startswith(month)]
    rows, to_create = [], []
    for md, mt in sorted(saved_meetings(in_month)):
        r = meeting_rows(in_month, md, mt)
        meta = get_meeting_meta(md, mt)
        _filled, _needed = fill_counts(r)
        rows.append({
            "Date": fmt_date(md), "Meeting": mt,
            "Filled": round(100 * _filled / max(_needed, 1)),
            "Open slots": _needed - _filled,
            "Aux. classroom": "Yes" if (r["hall"] != MAIN_HALL).any() else "",
            "Heading": meta.get("heading") or talk_text(meta),
        })

    for label, meeting, status in midweek_workbook_weeks(schedules_df):
        md = meeting.isoformat()
        if not md.startswith(month) or status == "saved":
            continue
        if status == "no meeting":
            rows.append({"Date": fmt_date(md), "Meeting": MIDWEEK, "Filled": None,
                         "Open slots": None, "Aux. classroom": "",
                         "Heading": f"{label} · {event_label(md)}"})
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
    for _pid, start, end, _note, kind in get_no_meeting_periods():
        if start > month_end or end < month_start:
            continue
        label = fmt_date(start)
        if label in shown:
            continue
        span = "" if start == end else f" – {fmt_date(end)}"
        rows.append({"Date": label, "Meeting": "—", "Filled": None,
                     "Open slots": None, "Aux. classroom": "",
                     "Heading": event_text(kind) + span})

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
                        flash("Created " + ", ".join(made)
                                   + ". Open each week to check it before printing.")
                        st.rerun()
                    else:
                        st.warning("Those weeks are no longer in the workbook.")
        cols = st.columns(min(len(to_create), 4))
        for i, (md, label) in enumerate(to_create):
            if cols[i % len(cols)].button(f"Create {fmt_date(md, short=True)}",
                                          icon=":material/add:",
                                          key=f"create_{md}", width="stretch"):
                go("Create or edit", schedule_mode="Create new",
                   new_meeting_type=MIDWEEK,
                   new_meeting_date=datetime.strptime(md, "%Y-%m-%d").date())

        with st.expander("Is one of these an assembly or convention week?"):
            mark_event_week_form(
                "month", datetime.strptime(to_create[0][0], "%Y-%m-%d").date())

    st.divider()
    if st.button("Print this month", icon=":material/print:"):
        go("Slips and printing", print_scope="A whole month", print_month=month)
