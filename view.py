# -*- coding: utf-8 -*-
"""Slips and printing: slips, schedule sheets, the S-140, the CSV and messages.

Public-talk documents (reminders, letters, the checklist) are on the Public
talks page.
"""
from datetime import datetime

import pandas as pd
import streamlit as st

from constants import MAIN_HALL, MIDWEEK, WEEKEND
from db import (
    get_meeting_meta,
    get_schedules,
    get_setting,
    load_template,
    meeting_label,
    saved_meetings,
    talk_text,
)
from s140 import S140Error, fill_s140
from sheets_pdf import (
    build_s140_data,
    generate_schedule_pdf,
    month_assignments_for,
    split_by_type,
    whatsapp_month_text,
)
from slips import S89Error, slip_rows_for, slips_pdf
from ui import go, page_header
from utils import fmt_date, make_slot, slot_label


def render(students_df, t, selected_lang, aux_default):
    page_header("Slips and printing",
                "Slips, schedule sheets, the S-140, the CSV and monthly messages — for one meeting or a whole month.")
    schedules_df = get_schedules()
    meetings = saved_meetings(schedules_df)
    if not meetings:
        st.info("No schedules have been created yet.")
        st.stop()

    # what to print: one meeting or a whole month, shared by every tab
    scope = st.radio("Print", ["One meeting", "A whole month"], horizontal=True,
                     key="print_scope")
    if scope == "One meeting":
        if st.session_state.get("view_meeting") not in meetings:
            st.session_state.pop("view_meeting", None)
        selected = st.selectbox("Meeting", meetings, format_func=meeting_label,
                                key="view_meeting")
        chosen = [selected]
        label_for_file = selected[0]
        month = selected[0][:7]
    else:
        months = sorted({d[:7] for d, _ in meetings}, reverse=True)
        month = st.selectbox(
            "Month", months, key="print_month",
            format_func=lambda ym: datetime.strptime(ym, "%Y-%m").strftime("%B %Y"))
        chosen = [m for m in meetings if m[0].startswith(month)]
        label_for_file = month
        st.caption(", ".join(meeting_label(m) for m in sorted(chosen)))

    chosen_set = set(chosen)
    in_scope = pd.Series(
        [(d, k) in chosen_set for d, k in zip(schedules_df["meeting_date"],
                                              schedules_df["meeting_type"])],
        index=schedules_df.index, dtype=bool)
    rows = schedules_df[in_scope]

    if scope == "One meeting":
        meeting_summary(chosen[0], rows)

    tab_print, tab_export, tab_messages = st.tabs(
        ["Slips & sheets", "S-140 & CSV", "Messages"])
    with tab_print:
        slips_and_sheets(chosen, rows, schedules_df, t, selected_lang,
                         label_for_file)
    with tab_export:
        s140_and_csv(meetings, schedules_df, t, selected_lang, month)
    with tab_messages:
        monthly_messages(meetings, schedules_df, students_df, month)


def meeting_summary(meeting, rows):
    meeting_date, meeting_type = meeting
    meta = get_meeting_meta(meeting_date, meeting_type)
    if meta.get("heading"):
        st.caption(meta["heading"])
    if meeting_type == WEEKEND:
        st.markdown(f"**Public talk:** {talk_text(meta) or '— title not entered —'}")
    table = pd.DataFrame({
        "Part": [slot_label(make_slot(r.part_name, r.role or "", r.section,
                                      int(r.part_no) if pd.notna(r.part_no) else None,
                                      int(r.minutes) if pd.notna(r.minutes) else None,
                                      r.hall))
                 for r in rows.itertuples()],
        "Assigned to": rows["person"].fillna("— unassigned —").tolist(),
        "Assistant": [
            (r.assistant or "— needed —") if r.needs_assistant == 1 else ""
            for r in rows.itertuples()
        ],
    })
    st.dataframe(table, width="stretch", hide_index=True)
    if st.button("Edit this schedule", icon=":material/edit:"):
        go("Create or edit", schedule_mode="Edit saved", edit_meeting=meeting)


# ------------------------------------------------------------ slips & sheets
def slips_and_sheets(chosen, rows, schedules_df, t, selected_lang, label_for_file):
    st.subheader("S-89 assignment slips")
    slip_rows = slip_rows_for(rows)
    if not slip_rows:
        st.info("No student parts are assigned, so there are no slips to print.")
    else:
        n_aux = sum(1 for r in slip_rows if r["hall"] != MAIN_HALL)
        if n_aux:
            st.caption(f"{len(slip_rows) - n_aux} main hall and {n_aux} auxiliary "
                       "classroom slip(s); each has its room ticked.")
        try:
            slips = slips_pdf(slip_rows, t, selected_lang)
        except S89Error as exc:
            st.error(str(exc), icon=":material/upload_file:")
        else:
            st.download_button(
                f"Download {len(slip_rows)} slip(s) ({selected_lang})",
                icon=":material/receipt_long:", data=slips,
                file_name=f"S89_slips_{label_for_file}_{selected_lang}.pdf",
                mime="application/pdf",
            )

    st.divider()
    st.subheader("Printable schedule")
    midweek, weekend = split_by_type(chosen)
    two_up = False
    if len(midweek) > 1:
        two_up = st.checkbox(
            "Two midweek weeks per sheet", value=True, key="midweek_two_up",
            help="A week using the auxiliary classroom still prints on its own "
                 "sheet — it is too tall to pair without shrinking it.")
    st.caption("The midweek and weekend sheets download separately.")
    c1, c2 = st.columns(2)
    for column, picked, kind in ((c1, midweek, "Midweek"), (c2, weekend, "Weekend")):
        if not picked:
            column.button(f"{kind} schedule", disabled=True, width="stretch",
                          help=f"No {kind.lower()} meeting in this selection.",
                          key=f"no_{kind}")
            continue
        column.download_button(
            f"{kind} schedule ({len(picked)})", icon=":material/print:",
            data=generate_schedule_pdf(picked, schedules_df, t,
                                       compact=two_up and kind == "Midweek"),
            file_name=f"{kind.lower()}_schedule_{label_for_file}.pdf",
            mime="application/pdf", width="stretch", key=f"dl_{kind}",
        )


# --------------------------------------------------------------- S-140 & CSV
def s140_and_csv(meetings, schedules_df, t, selected_lang, month):
    st.subheader("S-140")
    midweek_months = sorted({m[0][:7] for m in meetings if m[1] == MIDWEEK},
                            reverse=True)
    if not midweek_months:
        st.info("Save a midweek schedule to fill the S-140.")
    else:
        s140_month = st.selectbox(
            "Month", midweek_months, key="s140_month",
            index=midweek_months.index(month) if month in midweek_months else 0,
            format_func=lambda ym: datetime.strptime(ym, "%Y-%m").strftime("%B %Y"))
        template, _ = load_template(f"s140_{selected_lang}")
        if not template:
            st.warning(f"No {selected_lang} S-140 template. Upload the blank "
                       ".docx under Admin.", icon=":material/upload_file:")
        else:
            s140_download(meetings, schedules_df, t, template, s140_month)

    st.divider()
    st.subheader("Spreadsheet")
    talks = {}
    for md, mt in meetings:
        if mt == WEEKEND:
            talks[(md, mt)] = talk_text(get_meeting_meta(md, mt))
    csv_df = schedules_df.assign(talk=[
        talks.get((r.meeting_date, r.meeting_type), "") if r.role == "Public Talk"
        else "" for r in schedules_df.itertuples()])[
        ["meeting_date", "meeting_type", "part_no", "part_name", "talk",
         "minutes", "section", "role", "hall", "person", "assistant"]]
    st.download_button(
        "All schedules as CSV", icon=":material/table_view:",
        data=csv_df.to_csv(index=False).encode("utf-8-sig"),  # BOM keeps ɛ/ɔ right
        file_name="meeting_schedule.csv", mime="text/csv")


def s140_download(meetings, schedules_df, t, template, s140_month):
    month_meetings = sorted(m for m in meetings
                            if m[1] == MIDWEEK and m[0].startswith(s140_month))
    data, skipped = build_s140_data(month_meetings, schedules_df,
                                    get_setting("congregation"))
    data["meeting_name"] = t.get("midweek_meeting", "Midweek Meeting")
    if skipped:
        st.warning("Skipped (need 3 Treasures parts and a Bible Study): "
                   + ", ".join(fmt_date(d) for d in skipped))
    if not data["weeks"]:
        st.info("Nothing to fill for that month.")
        return
    try:
        docx_bytes = fill_s140(template, data)
    except (S140Error, KeyError, IndexError) as exc:
        st.error(f"Couldn't fill the template: {exc}")
        return
    month_name = datetime.strptime(s140_month, "%Y-%m").strftime("%B %Y")
    st.download_button(
        f"S-140 for {month_name}", data=docx_bytes,
        icon=":material/description:", file_name=f"{month_name}.docx",
        mime="application/vnd.openxmlformats-officedocument."
             "wordprocessingml.document")


# ------------------------------------------------------------------ messages
def monthly_messages(meetings, schedules_df, students_df, month):
    st.subheader("Monthly assignments by WhatsApp")
    st.caption("Everything one person has in a month, parts and assisting, "
               "in one message — copy it and send it yourself. Public Talk "
               "reminders are on the Public talks page.")
    all_months = sorted({d[:7] for d, _ in meetings}, reverse=True)
    wa_month = st.selectbox(
        "Month", all_months,
        index=all_months.index(month) if month in all_months else 0,
        key="wa_month",
        format_func=lambda ym: datetime.strptime(ym, "%Y-%m").strftime("%B %Y"))
    in_month = schedules_df[schedules_df["meeting_date"].str.startswith(wa_month)]
    counts = pd.concat([in_month["student_id"], in_month["assistant_id"]]) \
        .dropna().astype(int).value_counts()
    people_in_month = students_df[students_df["id"].isin(counts.index)] \
        .sort_values("name")
    if people_in_month.empty:
        st.info("Nobody from the participants list has an assignment that month.")
        return
    wa_names = dict(zip(people_in_month["id"], people_in_month["name"]))
    wa_pick = st.selectbox(
        "Participant", list(wa_names), key="wa_person",
        format_func=lambda i: f"{wa_names[i]} ({counts[i]})")
    person = people_in_month[people_in_month["id"] == wa_pick].iloc[0]
    st.code(whatsapp_month_text(
        person["name"], person["gender"], wa_month,
        month_assignments_for(schedules_df, wa_pick, wa_month)),
        language=None, wrap_lines=True)
    st.caption("The copy button is at the top right of the box.")
