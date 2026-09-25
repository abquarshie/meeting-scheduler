# -*- coding: utf-8 -*-
"""Admin: backup and restore, settings, public talks, change log."""
from core import *  # noqa: F401,F403
from month import WEEKDAYS


def render(students_df, t, selected_lang, aux_default):
    page_header(tr("h_admin"), tr("sub_admin"))
    tab_data, tab_settings, tab_talks, tab_log = st.tabs(
        ["Data & backup", "Settings", "Public talks", "Change log"])

    with tab_data:
        st.subheader("Official S-89 blank")
        st.caption("Upload the fillable blank S-89 for each slip language and the "
                   "app prints on the real form, with its exact wording. Without "
                   "one it draws its own slip.")
        for language in TRANSLATIONS:
            stored, file_name = load_template(f"s89_{language}")
            c1, c2 = st.columns([4, 1])
            if stored:
                c1.success(f"{language}: **{file_name}**")
                if c2.button("Remove", key=f"rm_s89_{language}", width="stretch"):
                    delete_template(f"s89_{language}")
                    st.rerun()
            else:
                c1.info(f"{language}: no blank form uploaded.")
            blank = st.file_uploader(f"Blank S-89 ({language})", type=["pdf"],
                                     key=f"up_s89_{language}")
            if blank is not None:
                try:
                    per_page = check_s89_template(blank.getvalue())
                except S89Error as exc:
                    st.error(str(exc))
                else:
                    save_template(f"s89_{language}", blank.name, blank.getvalue())
                    st.success(f"Saved the {language} blank form — "
                               f"{per_page} slip(s) per page.")
                    st.rerun()

        st.subheader("S-140 template (Word)")
        st.caption("Upload the blank once per language and the Export page uses "
                   "it every month. It is a .docx, not a PDF, and the published "
                   "blank holds one week — the app repeats it for the month.")
        for language in TRANSLATIONS:
            stored, file_name = load_template(f"s140_{language}")
            c1, c2 = st.columns([4, 1])
            if stored:
                c1.success(f"{language}: **{file_name}**")
                if c2.button("Remove", key=f"rm_s140_{language}", width="stretch"):
                    delete_template(f"s140_{language}")
                    st.rerun()
            else:
                c1.info(f"{language}: no S-140 template uploaded.")
            s140_file = st.file_uploader(f"Blank S-140 ({language}, .docx)",
                                         type=["docx"], key=f"up_s140_{language}")
            if s140_file is not None:
                try:
                    blocks = check_s140_template(s140_file.getvalue())
                except S140Error as exc:
                    st.error(str(exc))
                else:
                    save_template(f"s140_{language}", s140_file.name,
                                  s140_file.getvalue())
                    st.success(f"Saved the {language} S-140 — "
                               f"{blocks} week block(s) in the blank.")
                    st.rerun()

        st.subheader("Backup file")
        st.download_button(
            "Download full backup (.json)", data=backup_bytes(), icon=":material/download:",
            file_name=f"meeting_scheduler_backup_{date.today()}.json",
            mime="application/json",
        )
        st.caption("Includes participants, schedules, away dates, suspensions, "
                   "the workbook, settings and the change log.")
        upload = st.file_uploader("Restore from a backup file", type=["json"],
                                  key="restore_upload")
        if upload is not None:
            try:
                data = json.loads(upload.getvalue().decode("utf-8"))
                st.info(f"Backup from {data.get('_created', 'unknown date')}: "
                        f"{len(data.get('students', []))} participants, "
                        f"{len(data.get('schedules', []))} schedule rows.")
                sure = st.checkbox("I understand this replaces all current data",
                                   key="restore_sure")
                if st.button("Restore this backup", type="primary", disabled=not sure):
                    counts = import_all(data)
                    st.success(f"Restored {counts.get('students', 0)} participants.")
            except (ValueError, UnicodeDecodeError) as exc:
                st.error(f"That file can't be restored: {exc}")

    with tab_settings:
        st.subheader("Printing")
        c1, c2 = st.columns(2)
        congregation = c1.text_input(
            "Congregation name", get_setting("congregation"),
            help="Printed at the top of every schedule sheet.")
        lang = c2.selectbox("Slip and schedule language", list(TRANSLATIONS),
                            index=list(TRANSLATIONS).index(
                                get_setting("slip_language", list(TRANSLATIONS)[0])
                                if get_setting("slip_language") in TRANSLATIONS else
                                list(TRANSLATIONS)[0]))
        aux_default = st.toggle(
            "Auxiliary classroom in use", value=get_setting("use_aux", "1") == "1",
            help="Default for new midweek schedules. Any week can still differ.")
        ga_on = st.toggle(
            "Convert 3 ) N to ɛ ɔ ŋ when saving names",
            value=get_setting("ga_convert", "0") == "1",
            help="Turn off if a name genuinely contains 3, ) or a capital N.")
        if st.button("Save printing settings"):
            set_setting("congregation", congregation)
            set_setting("slip_language", lang)
            set_setting("use_aux", "1" if aux_default else "0")
            set_setting("ga_convert", "1" if ga_on else "0")
            st.session_state["slip_lang"] = lang
            st.success("Saved.")
            st.rerun()

        st.subheader("Meeting days")
        st.caption("Used to place workbook weeks on the right day in the month view.")
        c1, c2 = st.columns(2)
        mid = c1.selectbox("Midweek meeting day", WEEKDAYS,
                           index=WEEKDAYS.index(get_setting("midweek_day", "Wednesday")))
        wkd = c2.selectbox("Weekend meeting day", WEEKDAYS,
                           index=WEEKDAYS.index(get_setting("weekend_day", "Sunday")))
        if st.button("Save meeting days"):
            set_setting("midweek_day", mid)
            set_setting("weekend_day", wkd)
            log_change("Meeting days changed", f"midweek {mid}, weekend {wkd}")
            st.success("Saved.")

        st.subheader("Weekend meeting")
        st.caption("Used on the invitation letter, printed from View "
                   "Schedules by the Talk Coordinator.")
        c1, c2 = st.columns(2)
        meeting_time = c1.text_input(
            "Public meeting time", get_setting("meeting_time", ""),
            placeholder="e.g. 6:30pm")
        hall_address = c2.text_input(
            "Kingdom Hall address", get_setting("hall_address", ""),
            placeholder="e.g. Hansen Road Near Palledium")
        signoff = st.text_input(
            "Talk Coordinator sign-off name",
            get_setting("talk_coordinator_signoff", "Bernard Mensah"),
            help="Signs every invitation letter. Update this here whenever "
                 "the Talk Coordinator changes.")
        c3, c4 = st.columns(2)
        phone = c3.text_input(
            "Talk Coordinator phone", get_setting("talk_coordinator_phone", ""),
            placeholder="e.g. 055 307 8753",
            help="Printed on the invitation letter, for the other "
                 "congregation to reach out with questions.")
        email = c4.text_input(
            "Talk Coordinator email", get_setting("talk_coordinator_email", ""),
            placeholder="e.g. niio@jwpub.org")
        if st.button("Save weekend meeting details"):
            set_setting("meeting_time", meeting_time)
            set_setting("hall_address", hall_address)
            set_setting("talk_coordinator_signoff", signoff)
            set_setting("talk_coordinator_phone", phone)
            set_setting("talk_coordinator_email", email)
            st.success("Saved.")

        st.subheader("Rotation")
        gap_days = st.number_input(
            "Days before someone may take the same part again", min_value=1,
            max_value=90, value=same_role_gap_days(), step=1,
            help="Suggest and the 🔴 marker treat a part as \"too soon\" within "
                 "this many days of someone's last turn at it. The rest of the "
                 "colour-coding (2 weeks ago, 3 weeks ago, and so on) doesn't "
                 "change — this only moves where the red/green line falls.")
        if st.button("Save rotation setting"):
            set_setting("same_role_gap_days", str(int(gap_days)))
            log_change("Rotation rest period changed", f"{int(gap_days)} day(s)")
            st.success("Saved.")

        st.subheader("Assemblies & conventions")
        st.caption("Weeks with no meeting at all. Once recorded here, they stop "
                   "showing up as a schedule still to create, on the Dashboard "
                   "and in Month overview.")
        periods = get_no_meeting_periods()
        if periods:
            for pid, start, end, note in periods:
                c1, c2 = st.columns([4, 1])
                span = fmt_date(start) if start == end else \
                    f"{fmt_date(start, short=True)} – {fmt_date(end)}"
                c1.write(span + (f" — {note}" if note else ""))
                if c2.button("Remove", key=f"rm_nomeeting_{pid}", width="stretch"):
                    delete_no_meeting_period(pid)
                    st.rerun()
        else:
            st.caption("None recorded.")
        with st.form("add_no_meeting", clear_on_submit=True):
            d1, d2 = st.columns(2)
            start = d1.date_input("First day with no meeting")
            end = d2.date_input("Last day with no meeting", start)
            note = st.text_input("Note", placeholder="e.g. Circuit Assembly")
            if st.form_submit_button("Add"):
                add_no_meeting_period(start, end, note)
                st.success("Saved.")
                st.rerun()

    with tab_talks:
        st.caption("The outlines your congregation uses. Once they are here, "
                   "creating a weekend schedule is picking one from the list.")
        talks = get_talks()
        table = st.data_editor(
            pd.DataFrame(talks or [], columns=["number", "title"]),
            num_rows="dynamic", width="stretch", hide_index=True,
            key="talks_editor",
            column_config={
                "number": st.column_config.TextColumn("No.", required=True,
                                                      width="small"),
                "title": st.column_config.TextColumn("Title", width="large"),
            },
        )
        if st.button("Save talks", type="primary"):
            kept, seen = [], set()
            for row in table.to_dict("records"):
                number = nfc(str(row.get("number") or ""))
                if not number or number in seen:
                    continue
                seen.add(number)
                save_talk(number, row.get("title") or "")
                kept.append(number)
            for number, _ in talks:
                if number not in seen:
                    delete_talk(number)
            st.success(f"Saved {len(kept)} talk(s).")
            st.rerun()
        st.caption("Add a row with the + at the bottom; clear a row's number "
                   "to remove that talk.")

        st.divider()
        st.markdown("**Load a list**")
        st.caption("A CSV with a `number` and a `title` column. Re-importing the "
                   "same numbers updates their titles, so corrections are one "
                   "upload rather than a hunt through the table.")
        csv_file = st.file_uploader("Talks CSV", type=["csv"], key="talks_csv")
        replace = st.checkbox("Replace the whole list", key="talks_replace",
                              help="Otherwise the file is merged into what is "
                                   "already there.")
        if csv_file is not None and st.button("Import talks", type="primary"):
            try:
                frame = pd.read_csv(csv_file, dtype=str).fillna("")
                columns = {c.strip().lower(): c for c in frame.columns}
                if "number" not in columns or "title" not in columns:
                    raise ValueError("needs a 'number' and a 'title' column")
                pairs = list(zip(frame[columns["number"]], frame[columns["title"]]))
            except Exception as exc:
                st.error(f"Couldn't read that CSV: {str(exc)[:160]}")
            else:
                total, added = import_talks(pairs, replace=replace)
                st.success(f"Imported {total} talk(s), {added} new.")
                st.rerun()

        if talks:
            st.download_button(
                "Download the list as CSV",
                data=pd.DataFrame(talks, columns=["number", "title"]).to_csv(
                    index=False).encode("utf-8-sig"),
                file_name="public_talks.csv", mime="text/csv",
                icon=":material/download:")

    with tab_log:
        log = get_log()
        if log.empty:
            st.info("No changes recorded yet.")
        else:
            who = st.multiselect("Who", sorted(u for u in log["user"].unique() if u),
                                 key="log_who")
            if who:
                log = log[log["user"].isin(who)]
            view = log.rename(columns={"ts": "When", "user": "Who",
                                       "action": "What", "details": "Details"})
            view["When"] = view["When"].str.replace("T", " ")
            st.dataframe(view, width="stretch", hide_index=True)
            st.download_button("Download change log (CSV)",
                               view.to_csv(index=False).encode("utf-8-sig"),
                               file_name="change_log.csv", mime="text/csv")
