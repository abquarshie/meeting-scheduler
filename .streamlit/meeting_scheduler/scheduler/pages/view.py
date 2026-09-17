# -*- coding: utf-8 -*-
"""View Schedules page."""
from scheduler.core import *  # noqa: F401,F403


def render(students_df, t, selected_lang, aux_default):
    st.header(tr("h_view"))
    schedules_df = get_schedules()
    meetings = saved_meetings(schedules_df)
    if not meetings:
        st.info("No schedules have been created yet.")
        st.stop()

    selected = st.selectbox("Meeting", meetings, format_func=meeting_label)
    meeting_date, meeting_type = selected
    rows = schedules_df[(schedules_df["meeting_date"] == meeting_date)
                        & (schedules_df["meeting_type"] == meeting_type)]
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
    if st.button("✏️ Edit this schedule"):
        go("Schedule", schedule_mode="Edit saved", edit_meeting=selected)

    st.divider()
    st.subheader("🧾 S-89 assignment slips")
    student_rows = rows[(rows["student_part"] == 1) & rows["person"].notna()]
    if student_rows.empty:
        st.info("No student parts are assigned for this meeting, so there are no slips to print.")
    else:
        slip_rows = [
            {"person": r.person, "assistant": r.assistant,
             "part_no": int(r.part_no) if pd.notna(r.part_no) else None,
             "part_name": r.part_name, "meeting_date": meeting_date, "hall": r.hall}
            for r in student_rows.sort_values(["hall", "sort_order"]).itertuples()
        ]
        n_aux = sum(1 for r in slip_rows if r["hall"] == AUX_HALL)
        if n_aux:
            st.caption(f"{len(slip_rows) - n_aux} main hall and {n_aux} auxiliary "
                       "classroom slip(s); each has its room ticked.")
        st.download_button(
            f"📄 Download {len(slip_rows)} slip(s) ({selected_lang})",
            data=generate_slips_pdf(slip_rows, t),
            file_name=f"S89_slips_{meeting_date}_{selected_lang}.pdf",
            mime="application/pdf",
        )

    st.divider()
    st.subheader("💬 Reminders to copy")
    st.caption("One message per person. Tap to expand, copy, and paste into WhatsApp.")
    reminded = reminder_rows(rows)
    if reminded.empty:
        st.info("Assign parts to generate reminders.")
    else:
        messages = [reminder_message(r, meeting_type, meeting_date, meta)
                    for r in reminded.itertuples()]
        with st.expander(f"All {len(messages)} reminders in one block"):
            st.code("\n\n---\n\n".join(m for _, m in messages), language=None)
        for r, (part_txt, msg) in zip(reminded.itertuples(), messages):
            with st.expander(f"{r.person} — {part_txt}"):
                st.code(msg, language=None)

    st.divider()
    st.subheader("🖨️ Printable schedule")
    chosen = st.multiselect("Meetings to include", meetings, default=[selected],
                            format_func=meeting_label)
    if chosen:
        chosen = sorted(chosen)
        st.download_button(
            "📄 Download schedule PDF",
            data=generate_schedule_pdf(chosen, schedules_df),
            file_name=f"schedule_{chosen[0][0]}_to_{chosen[-1][0]}.pdf",
            mime="application/pdf",
        )
