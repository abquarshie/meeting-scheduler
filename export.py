# -*- coding: utf-8 -*-
"""Export page."""
from core import *  # noqa: F401,F403


def render(students_df, t, selected_lang, aux_default):
    page_header(tr("h_export"), tr("sub_export"))
    schedules_df = get_schedules()
    if schedules_df.empty:
        st.info("No schedule data to export yet.")
        st.stop()

    st.subheader("CSV")
    talks = {}
    for md, mt in saved_meetings(schedules_df):
        if mt == WEEKEND:
            talks[(md, mt)] = talk_text(get_meeting_meta(md, mt))
    schedules_df = schedules_df.assign(talk=[
        talks.get((r.meeting_date, r.meeting_type), "") if r.role == "Public Talk" else ""
        for r in schedules_df.itertuples()])
    csv_df = schedules_df[["meeting_date", "meeting_type", "part_no", "part_name", "talk",
                           "minutes", "section", "role", "hall", "person", "assistant"]]
    st.download_button(
        "Download all schedules as CSV",
        data=csv_df.to_csv(index=False).encode("utf-8-sig"),  # BOM keeps ɛ/ɔ right in Excel
        file_name="meeting_schedule.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("S-140 (Word)")
    midweek = [m for m in saved_meetings(schedules_df) if m[1] == MIDWEEK]
    if not midweek:
        st.info("Save at least one midweek schedule first.")
        st.stop()
    months = sorted({m[0][:7] for m in midweek}, reverse=True)
    month = st.selectbox(
        "Month", months,
        format_func=lambda ym: datetime.strptime(ym, "%Y-%m").strftime("%B %Y"))
    month_meetings = sorted(m for m in midweek if m[0].startswith(month))
    st.caption("Weeks: " + ", ".join(fmt_date(m[0]) for m in month_meetings))

    congregation = get_setting("congregation")
    if not congregation:
        st.warning("Set the congregation name under Admin → Meeting days "
                   "before filling the S-140.", icon=":material/settings:")
    # the published blank clears that row on a week without the classroom, so
    # there is nothing for a group label to fill
    group_label = ""
    template, template_name = load_template(f"s140_{selected_lang}")
    if template:
        st.caption(f"Using the stored {selected_lang} template: "
                   f"**{template_name}** (change it under Admin).")
    else:
        st.warning(f"No {selected_lang} S-140 template stored. Upload the blank "
                   ".docx once under Admin → S-140 template.",
                   icon=":material/upload_file:")
    widen = st.checkbox("Widen title and name columns", value=True)

    data, skipped = build_s140_data(month_meetings, schedules_df, congregation,
                                    group_label)
    data["meeting_name"] = t.get("midweek_meeting", "Midweek Meeting")
    if skipped:
        st.warning("Skipped (need 3 Treasures parts and a Bible Study): "
                   + ", ".join(fmt_date(d) for d in skipped))

    col_a, col_b = st.columns(2)
    col_b.download_button(
        "Download data.json", data=json.dumps(data, ensure_ascii=False, indent=2),
        file_name="data.json", mime="application/json", width="stretch",
    )
    if template and data["weeks"]:
        try:
            docx_bytes = fill_s140(template, data, widen=widen)
        except (S140Error, KeyError, IndexError) as exc:
            st.error(f"Couldn't fill the template: {exc}")
        else:
            month_name = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
            col_a.download_button(
                f"Download {month_name}.docx", data=docx_bytes, icon=":material/description:",
                file_name=f"{month_name}.docx", width="stretch",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
