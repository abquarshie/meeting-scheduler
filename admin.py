# -*- coding: utf-8 -*-
"""Admin: Google Sheets sync, backup and restore, settings, wording, change log."""
from scheduler.core import *  # noqa: F401,F403
from scheduler.pages.month import WEEKDAYS


def render(students_df, t, selected_lang, aux_default):
    st.header(tr("h_admin"))
    tab_data, tab_settings, tab_words, tab_log = st.tabs(
        ["Data & backup", "Meeting days", "Interface wording", "Change log"])

    with tab_data:
        st.subheader("☁️ Google Sheets")
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

        st.subheader("💾 Backup file")
        st.download_button(
            "Download full backup (.json)", data=backup_bytes(),
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

    with tab_words:
        lang = st.selectbox("Language", [l for l in UI_LANGUAGES if l != "English"],
                            key="words_lang")
        current = ui_overrides(lang)
        table = pd.DataFrame([
            {"key": k, "English": v, lang: current.get(k, "")}
            for k, v in UI_TEXT.items()
        ])
        edited = st.data_editor(
            table, hide_index=True, width="stretch", key=f"words_{lang}",
            disabled=["key", "English"],
            column_config={"key": None},
        )
        st.caption("Leave a box empty to keep the English wording. Choose the "
                   "interface language in the sidebar settings.")
        if st.button(f"Save {lang} wording", type="primary"):
            save_ui_overrides(lang, dict(zip(edited["key"], edited[lang].fillna(""))))
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
