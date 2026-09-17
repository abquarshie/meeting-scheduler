# -*- coding: utf-8 -*-
"""Manage Participants page."""
from core import *  # noqa: F401,F403


def render(students_df, t, selected_lang, aux_default):
    page_header(tr("h_participants"), tr("sub_participants"))
    tab_add, tab_edit, tab_list = st.tabs(["Add", "Edit / deactivate", "List"])

    with tab_add:
        existing_families = family_names(students_df)
        with st.form("add_student_form", clear_on_submit=True):
            name = st.text_input("Full name")
            c1, c2 = st.columns(2)
            gender = c1.selectbox("Category", CATEGORIES)
            groups = c2.multiselect("Group", GROUPS,
                                    help="Leave empty for an adult publisher.")
            with st.container(border=True):
                family = pick_family("", existing_families, None, "add_family")
            privileges = st.multiselect("Privileges", PRIVILEGES)
            if st.form_submit_button("Add participant"):
                if not nfc(name):
                    st.error("Enter a name.")
                else:
                    if nfc(name).lower() in students_df["name"].str.lower().tolist():
                        st.warning(f"There is already someone called {name}; added anyway.")
                    add_student(name, gender, privileges, family, groups)
                    st.success(f"Added {name}.")
                    st.rerun()

    with tab_edit:
        if students_df.empty:
            st.info("No participants yet.")
        else:
            names = dict(zip(students_df["id"], students_df["name"]))
            sid = st.selectbox(
                "Participant", students_df["id"].tolist(),
                format_func=lambda i: names[i]
                + ("" if students_df.loc[students_df["id"] == i, "active"].iloc[0] == 1
                   else " (inactive)"),
            )
            row = students_df[students_df["id"] == sid].iloc[0]
            with st.form(f"edit_student_{sid}"):
                e_name = st.text_input("Full name", row["name"])
                e_gender = st.selectbox(
                    "Category", CATEGORIES,
                    index=CATEGORIES.index(row["gender"]) if row["gender"] in CATEGORIES else 0,
                )
                e_groups = st.multiselect("Group", GROUPS, default=row["group_list"],
                                          help="Leave empty for an adult publisher.")
                with st.container(border=True):
                    e_family = pick_family("", family_names(students_df), row["family"],
                                           f"edit_family_{sid}")
                e_priv = st.multiselect("Privileges", PRIVILEGES, default=row["privilege_list"])
                e_active = st.checkbox("Active (shown when assigning parts)",
                                       value=bool(row["active"]))
                if st.form_submit_button("Save changes"):
                    if not nfc(e_name):
                        st.error("Name can't be empty.")
                    else:
                        update_student(sid, e_name, e_gender, e_priv, e_active,
                                       e_family, e_groups)
                        st.success("Saved. Existing schedules show the updated name.")
                        st.rerun()

            row_d = row.to_dict()
            with st.expander("Suspension", expanded=is_suspended(row_d, date.today())):
                status = suspension_text(row_d)
                if status:
                    st.warning(status)
                sus = st.checkbox("Suspended (no parts or assisting)",
                                  value=bool(row_d.get("suspended")) and bool(status),
                                  key=f"sus_{sid}")
                until = None
                if sus:
                    open_ended = st.checkbox(
                        "No end date", key=f"sus_open_{sid}",
                        value=not (isinstance(row_d.get("suspended_until"), str)
                                   and row_d.get("suspended_until")))
                    if not open_ended:
                        saved_until = row_d.get("suspended_until")
                        default_until = (datetime.strptime(saved_until, "%Y-%m-%d").date()
                                         if isinstance(saved_until, str) and saved_until
                                         else date.today() + timedelta(days=90))
                        until = st.date_input("Suspended until (inclusive)", default_until,
                                              key=f"sus_until_{sid}").isoformat()
                    clash = upcoming_assignments(sid, until)
                    if clash:
                        st.info("Already scheduled in this period — reassign these: "
                                + "; ".join(f"{fmt_date(d)} {t.split()[0].lower()}: {p}"
                                            for d, t, p in clash))
                if st.button("Save suspension", key=f"save_sus_{sid}"):
                    set_suspension(sid, sus, until)
                    st.success("Suspension lifted." if not sus else "Suspension saved.")
                    st.rerun()

            with st.expander("Away dates (dropped from those meetings)"):
                current_away = unavailable_dates(sid)
                if current_away:
                    st.caption("Currently away: " + away_summary(current_away))
                period = st.date_input(
                    "Add an away period (pick the first and last day)",
                    value=(), key=f"away_{sid}",
                )
                a1, a2 = st.columns(2)
                if a1.button("Add period", key=f"add_away_{sid}"):
                    if len(period) == 0:
                        st.error("Pick a start date first.")
                    else:
                        start = period[0]
                        end = period[1] if len(period) > 1 else period[0]
                        days = [(start + timedelta(days=n)).isoformat()
                                for n in range((end - start).days + 1)]
                        set_unavailable(sid, sorted(set(current_away) | set(days)))
                        st.success("Away period added.")
                        st.rerun()
                if current_away and a2.button("Clear all", key=f"clear_away_{sid}"):
                    set_unavailable(sid, [])
                    st.rerun()

            used = student_usage_count(sid)
            with st.expander("Delete permanently"):
                if used:
                    st.info(
                        f"{row['name']} appears in {used} saved assignment(s). "
                        "Untick 'Active' instead so the history stays intact."
                    )
                elif st.button("Delete participant", type="primary"):
                    delete_student(sid)
                    st.warning("Participant deleted.")
                    st.rerun()

    with tab_list:
        if students_df.empty:
            st.info("No participants yet.")
        else:
            show = st.radio("Show", ["Everyone", "Families", "Adults"] + GROUPS + ["Suspended"],
                            horizontal=True, key="participant_filter")
            last = last_assignment_dates(exclude_date="")
            df = students_df
            if show == "Families":
                df = df[df["family"].notna()]
            elif show == "Adults":
                df = df[df["group_list"].apply(len) == 0]
            elif show == "Suspended":
                today_iso = date.today().isoformat()
                df = df[[is_suspended(r, today_iso) for r in df.to_dict("records")]]
            elif show in GROUPS:
                df = df[df["group_list"].apply(lambda g: show in g)]
            view = df.assign(
                group=df["group_list"].apply(lambda g: ", ".join(g) or "Adult"),
                last_assignment=df["id"].map(
                    lambda i: fmt_date(last[i]) if i in last else ""),
                status=[("Inactive" if r["active"] != 1 else
                         suspension_text(r) or "Active")
                        for r in df.to_dict("records")],
                privileges=df["privilege_list"].apply(", ".join),
                family=df["family"].fillna(""),
            )
            cols = ["name", "gender", "group", "family", "privileges",
                    "last_assignment", "status"]
            if df.empty:
                st.info("Nobody in this group yet.")
            elif show == "Families":
                for fam_name, members in view.sort_values("family").groupby("family"):
                    st.markdown(f"**{fam_name}** · {len(members)} member(s)")
                    st.dataframe(members[[c for c in cols if c != "family"]],
                                 width="stretch", hide_index=True)
            else:
                st.caption(f"{len(view)} participant(s)")
                st.dataframe(view[cols], width="stretch", hide_index=True)
