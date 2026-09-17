# -*- coding: utf-8 -*-
"""How often each person has had parts, to spot anyone left out or overused."""
from scheduler.core import *  # noqa: F401,F403


def build_report(students_df, schedules_df, start, end):
    period = schedules_df[(schedules_df["meeting_date"] >= start)
                          & (schedules_df["meeting_date"] <= end)]
    today = date.today().isoformat()
    records = []
    for s_ in students_df.to_dict("records"):
        sid = s_["id"]
        own = period[period["student_id"] == sid]
        assisting = period[period["assistant_id"] == sid]
        dates = list(own["meeting_date"]) + list(assisting["meeting_date"])
        status = ("Inactive" if s_["active"] != 1
                  else suspension_text(s_, today) or "Active")
        rec = {
            "Name": s_["name"], "Category": s_["gender"],
            "Group": ", ".join(s_["group_list"]) or "Adult",
            "Status": status,
            "Parts": len(own), "Assisting": len(assisting),
            "Total": len(own) + len(assisting),
            "Last": fmt_date(max(dates)) if dates else "",
        }
        for role, n in own["role"].value_counts().items():
            rec[role] = int(n)
        records.append(rec)
    report = pd.DataFrame(records)
    if report.empty:
        return report
    role_cols = [c for c in report.columns if c in ROLE_RULES]
    report[role_cols] = report[role_cols].fillna(0).astype(int)
    order = ["Name", "Category", "Group", "Status", "Parts", "Assisting",
             "Total", "Last"] + [r for r in ROLES if r in role_cols]
    return report[order].sort_values(["Total", "Name"])


def render(students_df, t, selected_lang, aux_default):
    st.header(tr("h_reports"))
    schedules_df = get_schedules()
    if students_df.empty:
        st.info("No participants yet.")
        return

    c1, c2 = st.columns([2, 3])
    span = c1.radio("Period", ["Last 3 months", "Last 6 months", "Last 12 months",
                               "Custom"], index=1, horizontal=False, key="report_span")
    today = date.today()
    if span == "Custom":
        rng = c2.date_input("From – to", (today - timedelta(days=182), today),
                            key="report_range")
        if len(rng) != 2:
            st.info("Pick an end date.")
            return
        start, end = rng
    else:
        months = int(span.split()[1])
        start, end = today - timedelta(days=round(months * 30.4)), today
    include_future = c2.checkbox("Include assignments already planned after today",
                                 key="report_future")
    if include_future:
        end = date(9999, 12, 31)
    c2.caption(f"From {fmt_date(start.isoformat())}"
               + ("" if include_future else f" to {fmt_date(end.isoformat())}"))

    active_only = c2.checkbox("Active participants only", value=True, key="report_active")
    people = students_df[students_df["active"] == 1] if active_only else students_df
    categories = c2.multiselect("Category", CATEGORIES, default=CATEGORIES,
                                key="report_cat")
    people = people[people["gender"].isin(categories)]

    report = build_report(people, schedules_df, start.isoformat(), end.isoformat())
    if report.empty:
        st.info("Nobody matches these filters.")
        return
    none = report[report["Total"] == 0]
    if not none.empty:
        st.warning(f"{len(none)} person(s) had no assignment in this period: "
                   + ", ".join(none["Name"]))
    st.dataframe(report, width="stretch", hide_index=True)
    st.download_button("Download report (CSV)",
                       report.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"assignment_report_{start}_{end}.csv",
                       mime="text/csv")

    st.divider()
    st.subheader("Person history")
    names = dict(zip(students_df["id"], students_df["name"]))
    pid = st.selectbox("Participant", list(names), format_func=names.get,
                       key="report_person")
    history = role_history(pid, limit=100)
    if not history:
        st.info("No assignments yet.")
    else:
        st.dataframe(pd.DataFrame([
            {"Date": fmt_date(d), "Part": part,
             "Room": HALL_NAMES.get(hall or MAIN_HALL, "")}
            for d, part, hall in history
        ]), width="stretch", hide_index=True)
