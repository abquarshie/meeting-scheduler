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
    else:
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

    # ---- speaker reminders, guest letter, annual checklist (both roles) -----
    st.divider()
    st.subheader("Speaker reminders")
    st.caption("A WhatsApp message for anyone with a Public Talk at least a "
               "week away — copy it and send it yourself.")
    reminders = upcoming_talk_reminders(schedules_df, min_days=7)
    if not reminders:
        st.info("Nobody has a Public Talk at least a week away yet.")
    else:
        for cand in reminders:
            with st.container(border=True):
                st.markdown(f"**{cand['person']}** — {fmt_date(cand['meeting_date'])}"
                            + (" · guest speaker" if cand["is_guest"] else ""))
                st.code(whatsapp_reminder_text(cand), language=None)

    st.divider()
    st.subheader("Guest speaker letter")
    if scope != "One meeting" or chosen[0][1] != WEEKEND:
        st.caption("Select a single weekend meeting above to print its letter.")
    else:
        talk_rows = rows[(rows["role"] == "Public Talk") & rows["person"].notna()]
        if talk_rows.empty:
            st.info("No Public Talk speaker assigned to this meeting yet.")
        elif not clean_value(getattr(talk_rows.iloc[0], "visitor", "")):
            st.caption("This meeting's speaker is a congregation participant, "
                       "not a guest — no letter needed.")
        else:
            talk_row = talk_rows.iloc[0]
            meeting_date = chosen[0][0]
            meta = get_meeting_meta(meeting_date, WEEKEND)
            candidate = {
                "meeting_date": meeting_date, "person": talk_row["person"],
                "talk_number": clean_value(meta.get("talk_number")),
                "talk_title": clean_value(meta.get("talk_title")),
            }
            meeting_time = get_setting("meeting_time", "")
            hall_address = get_setting("hall_address", "")
            signoff = get_setting("talk_coordinator_signoff", "Bernard Mensah")
            missing = [label for label, val in
                      (("public meeting time", meeting_time),
                       ("Kingdom Hall address", hall_address),
                       ("Talk Coordinator sign-off name", signoff)) if not val]
            if missing:
                st.warning("Set the " + ", ".join(missing) + " under Admin → "
                           "Settings → Weekend meeting first.")
            else:
                letter = guest_letter_pdf(candidate, get_setting("congregation", ""),
                                          hall_address, meeting_time, signoff)
                st.download_button(
                    f"Letter for {talk_row['person']}", data=letter,
                    icon=":material/mail:",
                    file_name=(f"letter_{talk_row['person'].replace(' ', '_')}"
                              f"_{meeting_date}.pdf"),
                    mime="application/pdf")

    st.divider()
    st.subheader("Annual talk checklist")
    st.caption("Which talk was given when, so a repeat is easy to spot before "
               "the next one is scheduled. Nothing here is ever deleted.")
    period = st.radio("Period", ["Last 1 year", "Last 2 years"], horizontal=True,
                      key="checklist_years")
    years_n = 1 if period == "Last 1 year" else 2
    checklist_rows = talk_checklist_rows(schedules_df, years_n)
    if not checklist_rows:
        st.info("No talks recorded in this period yet.")
    else:
        st.dataframe(pd.DataFrame([
            {"Date": fmt_date(r["meeting_date"]), "No.": r["talk_number"],
             "Title": r["talk_title"], "Speaker": r["speaker"]}
            for r in checklist_rows
        ]), width="stretch", hide_index=True)
        st.download_button(
            f"Download checklist ({period})", icon=":material/checklist:",
            data=talk_checklist_pdf(checklist_rows, get_setting("congregation", ""),
                                    years_n),
            file_name=f"talk_checklist_{years_n}yr.pdf", mime="application/pdf")

    if weekend_only:
        return

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
