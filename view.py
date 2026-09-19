# -*- coding: utf-8 -*-
"""View Schedules page."""
from core import *  # noqa: F401,F403


def render(students_df, t, selected_lang, aux_default):
    page_header(tr("h_view"), tr("sub_view"))
    schedules_df = get_schedules()
    meetings = saved_meetings(schedules_df)
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
