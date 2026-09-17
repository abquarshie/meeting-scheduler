# -*- coding: utf-8 -*-
"""Upload PDF Brochure page."""
from core import *  # noqa: F401,F403


def render(students_df, t, selected_lang, aux_default):
    st.header(tr("h_workbook"))
    st.write(
        "Upload the Life and Ministry Meeting Workbook PDF. Numbered parts with "
        "their minutes are read for each week, and you can correct them below."
    )
    stored, stored_file = load_workbook()
    if stored:
        c1, c2 = st.columns([4, 1])
        c1.info(f"Workbook in use: **{stored_file or 'uploaded workbook'}** "
                f"({len(stored)} week(s)). Uploading another replaces it.")
        if c2.button("Remove", width="stretch"):
            save_workbook({}, "")
            st.rerun()

    uploaded_pdf = st.file_uploader("Choose PDF file", type=["pdf"])
    raw_text = ""
    if uploaded_pdf is not None:
        weeks, empty, raw_text = parse_brochure(uploaded_pdf.getvalue())
        file_id = f"{uploaded_pdf.name}:{uploaded_pdf.size}"
        if st.session_state.get("brochure_file") != file_id:
            st.session_state["brochure_file"] = file_id
            if weeks:
                first, sure = guess_first_monday(weeks, uploaded_pdf.name)
                save_workbook(assign_dates(dict(weeks), first), uploaded_pdf.name)
                set_setting("workbook_dates_sure", "1" if sure else "0")
                stored, stored_file = load_workbook()
        if not weeks:
            st.error(
                "No numbered parts with durations were found. The PDF may be scanned, "
                "or laid out differently. Schedules will use the standard part list."
            )
        else:
            st.success(f"Found parts for {len(weeks)} week(s).")
        if empty:
            st.warning("No parts found under: " + ", ".join(empty))
        if weeks and not any(w.get("month") in ENGLISH_MONTHS for w in weeks.values()):
            st.info("The week headings aren't in English, so sections are guessed from "
                    "part numbers and durations. Check them below.")

    if stored:
        st.subheader("Week dates")
        first_week = next(iter(stored.values()))
        if get_setting("workbook_dates_sure", "0") != "1":
            st.warning("The week dates were guessed. Check the first week below — "
                       "every other week follows from it.")
        d1, d2 = st.columns([2, 1])
        first_date = d1.date_input(
            f"First week ({next(iter(stored))}) begins on",
            datetime.strptime(first_week["start"], "%Y-%m-%d").date()
            if first_week.get("start") else date.today(),
            key=f"wbfirst|{stored_file}",
            help="The Monday of the first week in the workbook.",
        )
        if d2.button("Apply dates", width="stretch"):
            save_workbook(assign_dates(stored, first_date), stored_file)
            set_setting("workbook_dates_sure", "1")
            st.success("Week dates updated.")
            st.rerun()

        st.subheader("Weeks found")
        summary = pd.DataFrame([
            {"Week": label, "Dates": week_dates_text(w), "Parts": len(w["parts"]),
             "Numbers": ", ".join(str(p["part_no"]) for p in w["parts"]),
             "Missing": ", ".join(map(str, w.get("gaps", []))) or "—"}
            for label, w in stored.items()
        ])
        st.dataframe(summary, width="stretch", hide_index=True)
        if any(w.get("gaps") for w in stored.values()):
            st.warning("Some weeks have missing part numbers. Open the week below, "
                       "compare with the workbook text, and add the missing rows.")

        st.subheader("Review and correct a week")
        week = st.selectbox("Week", list(stored))
        left, right = st.columns([3, 2])
        with left:
            editor_df = pd.DataFrame(stored[week]["parts"])[
                ["part_no", "title", "minutes", "section", "role"]]
            edited = st.data_editor(
                editor_df, key=f"editor|{stored_file}|{week}", width="stretch",
                hide_index=True, num_rows="dynamic",
                column_config={
                    "part_no": st.column_config.NumberColumn("No.", min_value=1, step=1),
                    "title": st.column_config.TextColumn("Title", required=True),
                    "minutes": st.column_config.NumberColumn("Min", min_value=1, step=1),
                    "section": st.column_config.SelectboxColumn(
                        "Section", options=["Treasures", "Ministry", "Living"], required=True),
                    "role": st.column_config.SelectboxColumn(
                        "Role", options=ROLES, required=True),
                },
            )
            st.caption("Use the + row at the bottom to add a missing part.")
            if st.button("Save corrections for this week", type="primary"):
                clean = edited.dropna(subset=["title", "section", "role"])
                parts = sorted(
                    (make_slot(r.title, r.role, r.section,
                               int(r.part_no) if pd.notna(r.part_no) else None,
                               int(r.minutes) if pd.notna(r.minutes) else None)
                     for r in clean.itertuples()),
                    key=lambda p_: p_["part_no"] or 99,
                )
                numbers = [p_["part_no"] for p_ in parts if p_["part_no"]]
                top = max(numbers) if numbers else 0
                stored[week]["parts"] = parts
                stored[week]["gaps"] = [n for n in range(1, top + 1) if n not in numbers]
                save_workbook(stored, stored_file)
                st.success("Saved. Use 'Create Schedule' to assign this week.")
                st.rerun()
        with right:
            st.text_area("Workbook text for this week", stored[week].get("text", ""),
                         height=420, key=f"wbraw|{week}")

    if raw_text:
        with st.expander("View the whole extracted text"):
            st.text_area("Raw text", raw_text, height=350)
