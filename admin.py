# -*- coding: utf-8 -*-
"""Admin: Google Sheets sync, backup and restore, settings, wording, change log."""
from core import *  # noqa: F401,F403
from month import WEEKDAYS


def render(students_df, t, selected_lang, aux_default):
    page_header(tr("h_admin"), tr("sub_admin"))
    tab_data, tab_settings, tab_log = st.tabs(
        ["Data & backup", "Meeting days", "Change log"])

    with tab_data:
        st.subheader("Google Sheets")
        kind, text = status_text()
        getattr(st, kind)(text)
        if enabled():
            c1, c2 = st.columns(2)
            if c1.button("Copy everything to Google Sheets now", width="stretch"):
                try:
                    sent = push(force=True)
                    st.success(f"Copied {len(sent)} table(s).")
                except Exception as exc:
                    st.error(f"Sync failed: {exc}")
            if c2.button("Load everything from Google Sheets…", width="stretch"):
                st.session_state["confirm_pull"] = True
            if st.session_state.get("confirm_pull"):
                st.error("This replaces all data in the app with what's in the sheet.")
                y, n = st.columns(2)
                if y.button("Yes, load from the sheet", type="primary"):
                    try:
                        counts = import_all(pull())
                        remember_current_state()
                        st.session_state.pop("confirm_pull", None)
                        st.success(f"Loaded {counts.get('students', 0)} participants and "
                                   f"{counts.get('schedules', 0)} schedule rows.")
                    except Exception as exc:
                        st.error(f"Couldn't load: {exc}")
                if n.button("Cancel", key="cancel_pull"):
                    st.session_state.pop("confirm_pull", None)
                    st.rerun()
        else:
            st.caption("See the README for the one-time Google setup.")

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
