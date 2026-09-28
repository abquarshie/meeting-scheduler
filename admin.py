# -*- coding: utf-8 -*-
"""Admin: backup and restore, settings, change log."""
from core import *  # noqa: F401,F403
from month import WEEKDAYS


def render(students_df, t, selected_lang, aux_default):
    page_header(tr("h_admin"), tr("sub_admin"))
    tab_data, tab_settings, tab_log = st.tabs(
        ["Data & backup", "Settings", "Change log"])

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
