# -*- coding: utf-8 -*-
"""View Schedules page."""
from core import *  # noqa: F401,F403


def render(students_df, t, selected_lang, aux_default):
    page_header(tr("h_view"), tr("sub_view"))
    schedules_df = get_schedules()
    meetings = saved_meetings(schedules_df)
    weekend_only = current_role() == ROLE_TALKS
    if weekend_only:
        meetings = [m for m in meetings if m[1] == WEEKEND]
    if not meetings:
        st.info("No schedules have been created yet.")
        st.stop()

    # one page for printing, whichever scope you want
    scope = st.radio("Print", ["One meeting", "A whole month"], horizontal=True,
                     key="print_scope")
    if scope == "One meeting":
        if st.session_state.get("view_meeting") not in meetings:
            st.session_state.pop("view_meeting", None)
        selected = st.selectbox("Meeting", meetings, format_func=meeting_label,
                                key="view_meeting")
        chosen = [selected]
        label_for_file = selected[0]
    else:
        months = sorted({d[:7] for d, _ in meetings}, reverse=True)
        month = st.selectbox(
            "Month", months, key="print_month",
            format_func=lambda ym: datetime.strptime(ym, "%Y-%m").strftime("%B %Y"))
        chosen = [m for m in meetings if m[0].startswith(month)]
        label_for_file = month
        st.caption(", ".join(meeting_label(m) for m in sorted(chosen)))

    rows = schedules_df[schedules_df.apply(
        lambda r: (r["meeting_date"], r["meeting_type"]) in set(chosen), axis=1)]

    if scope == "One meeting":
        meeting_date, meeting_type = chosen[0]
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
            go("Schedule", schedule_mode="Edit saved", edit_meeting=chosen[0])

    st.divider()
    if not weekend_only:
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
    if weekend_only:
        if not weekend:
            st.info("No weekend meeting in this selection.")
        else:
            st.download_button(
                f"Weekend schedule ({len(weekend)})", icon=":material/print:",
                data=generate_schedule_pdf(weekend, schedules_df, t, compact=False),
                file_name=f"weekend_schedule_{label_for_file}.pdf",
                mime="application/pdf", width="stretch", key="dl_Weekend",
            )
        return

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

    # ---- the other two things a month produces -------------------------------
    st.divider()
    st.subheader("Other documents")
    c1, c2 = st.columns(2)

    talks = {}
    for md, mt in saved_meetings(schedules_df):
        if mt == WEEKEND:
            talks[(md, mt)] = talk_text(get_meeting_meta(md, mt))
    csv_df = schedules_df.assign(talk=[
        talks.get((r.meeting_date, r.meeting_type), "") if r.role == "Public Talk"
        else "" for r in schedules_df.itertuples()])[
        ["meeting_date", "meeting_type", "part_no", "part_name", "talk",
         "minutes", "section", "role", "hall", "person", "assistant"]]
    c1.download_button(
        "All schedules as CSV", icon=":material/table_view:",
        data=csv_df.to_csv(index=False).encode("utf-8-sig"),  # BOM keeps ɛ/ɔ right
        file_name="meeting_schedule.csv", mime="text/csv", width="stretch")

    midweek_months = sorted({m[0][:7] for m in meetings if m[1] == MIDWEEK},
                            reverse=True)
    if not midweek_months:
        c2.info("Save a midweek schedule to fill the S-140.")
        return
    with c2:
        s140_month = st.selectbox(
            "S-140 month", midweek_months, key="s140_month",
            format_func=lambda ym: datetime.strptime(ym, "%Y-%m").strftime("%B %Y"))
        template, template_name = load_template(f"s140_{selected_lang}")
        if not template:
            st.warning(f"No {selected_lang} S-140 template. Upload the blank "
                       ".docx under Admin.", icon=":material/upload_file:")
            return
        month_meetings = sorted(m for m in meetings
                                if m[1] == MIDWEEK and m[0].startswith(s140_month))
        data, skipped = build_s140_data(month_meetings, schedules_df,
                                        get_setting("congregation"), "")
        data["meeting_name"] = t.get("midweek_meeting", "Midweek Meeting")
        if skipped:
            st.warning("Skipped (need 3 Treasures parts and a Bible Study): "
                       + ", ".join(fmt_date(d) for d in skipped))
        if not data["weeks"]:
            st.info("Nothing to fill for that month.")
            return
        try:
            docx_bytes = fill_s140(template, data, widen=True)
        except (S140Error, KeyError, IndexError) as exc:
            st.error(f"Couldn't fill the template: {exc}")
        else:
            month_name = datetime.strptime(s140_month, "%Y-%m").strftime("%B %Y")
            st.download_button(
                f"S-140 for {month_name}", data=docx_bytes,
                icon=":material/description:", file_name=f"{month_name}.docx",
                width="stretch",
                mime="application/vnd.openxmlformats-officedocument."
                     "wordprocessingml.document")
