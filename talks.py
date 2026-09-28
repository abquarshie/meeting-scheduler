# -*- coding: utf-8 -*-
"""Public talks: everything the talk coordinator does, in one place.

The talk list, guest speakers coming to us, our own speakers going out, the
letters for both and the annual checklist used to be spread over Admin,
Participants and Slips and printing.
"""
from datetime import date

import pandas as pd
import streamlit as st

from constants import WEEKEND
from db import (
    add_outgoing_engagement,
    delete_outgoing_engagement,
    delete_talk,
    get_meeting_meta,
    get_outgoing_speakers,
    get_schedules,
    get_setting,
    get_talks,
    import_talks,
    outgoing_engagements,
    remove_outgoing_speaker,
    save_talk,
    set_outgoing_speaker,
    set_setting,
    talk_label,
)
from sheets_pdf import (
    clean_value,
    invitation_letter_pdf,
    outgoing_speakers_letter_pdf,
    talk_checklist_pdf,
    talk_matrix_rows,
    upcoming_talk_reminders,
    whatsapp_reminder_text,
)
from ui import go, page_header
from utils import fmt_date, nfc


def render(students_df, t, selected_lang, aux_default):
    page_header("Public talks",
                "Guest speakers, our outgoing speakers, their letters, the talk list and the annual checklist.")
    schedules_df = get_schedules()
    tab_coming, tab_outgoing, tab_checklist, tab_list, tab_details = st.tabs(
        ["Coming up", "Outgoing speakers", "Annual checklist", "Talk list",
         "Letter details"])

    with tab_coming:
        coming_up(schedules_df)
    with tab_outgoing:
        outgoing(students_df)
    with tab_checklist:
        checklist(schedules_df)
    with tab_list:
        talk_list()
    with tab_details:
        letter_details()


# ------------------------------------------------------------------ coming up
def coming_up(schedules_df):
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
    st.subheader("Invitation letter")
    st.caption("A letter to a guest speaker's congregation, asking them to "
               "release him for the visit.")
    talk_rows = schedules_df[(schedules_df["role"] == "Public Talk")
                             & schedules_df["person"].notna()]
    is_guest = talk_rows["visitor"].map(lambda v: bool(clean_value(v))).astype(bool)
    guests = talk_rows[is_guest].sort_values("meeting_date")
    if guests.empty:
        st.info("No weekend meeting has a guest speaker yet. Type the visiting "
                "speaker's name into the Public Talk part when creating the "
                "weekend schedule.")
        return

    dates = guests["meeting_date"].tolist()
    today = date.today().isoformat()
    upcoming = [d for d in dates if d >= today]
    pick = st.selectbox(
        "Weekend meeting", dates, key="letter_meeting",
        index=dates.index(upcoming[0]) if upcoming else len(dates) - 1,
        format_func=lambda d: f"{fmt_date(d)} — "
        + guests[guests["meeting_date"] == d].iloc[0]["person"])
    talk_row = guests[guests["meeting_date"] == pick].iloc[0]
    meta = get_meeting_meta(pick, WEEKEND)
    guest_congregation = clean_value(talk_row["visitor_congregation"])
    settings = {key: get_setting(key, default) for key, default in (
        ("meeting_time", ""), ("hall_address", ""),
        ("talk_coordinator_signoff", "Bernard Mensah"),
        ("talk_coordinator_phone", ""), ("talk_coordinator_email", ""))}
    missing = [label for label, key in (
        ("public meeting time", "meeting_time"),
        ("Kingdom Hall address", "hall_address"),
        ("Talk Coordinator sign-off name", "talk_coordinator_signoff"))
        if not settings[key]]
    if missing:
        st.warning("Fill in the " + ", ".join(missing)
                   + " in the Letter details tab first.")
    elif not guest_congregation:
        st.warning("This speaker's congregation isn't recorded yet — fill in "
                   "\"His congregation\" next to his name on the schedule.")
        if st.button("Open this schedule", icon=":material/edit:"):
            go("Create or edit", schedule_mode="Edit saved", edit_meeting=(pick, WEEKEND))
    else:
        candidate = {
            "meeting_date": pick, "person": talk_row["person"],
            "congregation": guest_congregation,
            "talk_number": clean_value(meta.get("talk_number")),
            "talk_title": clean_value(meta.get("talk_title")),
        }
        letter = invitation_letter_pdf(
            candidate, get_setting("congregation", ""), settings["hall_address"],
            settings["meeting_time"], settings["talk_coordinator_signoff"],
            settings["talk_coordinator_phone"], settings["talk_coordinator_email"])
        st.download_button(
            f"Letter to {guest_congregation}", data=letter, icon=":material/mail:",
            file_name=(f"invitation_{guest_congregation.replace(' ', '_')}"
                       f"_{pick}.pdf"),
            mime="application/pdf")


# ------------------------------------------------------------------ outgoing
def outgoing(students_df):
    st.caption("Brothers approved to give public talks at other "
               "congregations, and the talks they have ready. Marking a "
               "date one is going out keeps the local schedule from "
               "giving him a part that day.")
    brothers = students_df[(students_df["active"] == 1)
                           & (students_df["gender"] == "Brother")]
    if brothers.empty:
        st.info("No active brothers yet.")
        return
    names = dict(zip(brothers["id"], brothers["name"]))
    approved = get_outgoing_speakers()
    talks = get_talks()
    talk_titles = dict(talks)

    st.subheader("Approved speakers")
    if not approved:
        st.info("Nobody is marked as an approved outgoing speaker yet.")
    for sid, numbers in approved.items():
        if sid not in names:
            continue
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            talk_line = ", ".join(
                talk_label(n, talk_titles.get(n, "")) for n in numbers
            ) or "No talks listed yet."
            c1.markdown(f"**{names[sid]}**")
            c1.caption(talk_line)
            if c2.button("Remove", key=f"rm_outgoing_{sid}", width="stretch"):
                remove_outgoing_speaker(sid)
                st.rerun()

            with st.expander("Edit prepared talks"):
                if talks:
                    current = [n for n in numbers if n in talk_titles]
                    new_numbers = st.multiselect(
                        "Talks he has prepared", [n for n, _ in talks],
                        default=current,
                        format_func=lambda n: talk_label(n, talk_titles.get(n, "")),
                        key=f"outgoing_edit_talks_{sid}")
                    if st.button("Save talks", key=f"save_outgoing_talks_{sid}"):
                        set_outgoing_speaker(sid, new_numbers)
                        st.success("Saved.")
                        st.rerun()
                else:
                    st.caption("No talks in the list yet — add them in the "
                               "Talk list tab.")

            engagements = outgoing_engagements(sid)
            with st.expander(f"Going-out dates ({len(engagements)})"):
                for eid, d, cong, no in engagements:
                    e1, e2 = st.columns([4, 1])
                    text = fmt_date(d)
                    if cong:
                        text += f" — {cong}"
                    if no:
                        text += f" ({talk_label(no, talk_titles.get(no, ''))})"
                    e1.write(text)
                    if e2.button("Remove", key=f"rm_engagement_{eid}",
                                 width="stretch"):
                        delete_outgoing_engagement(eid)
                        st.rerun()
                if not engagements:
                    st.caption("None recorded.")
                st.markdown("**Add a date**")
                a1, a2, a3 = st.columns([2, 2, 2])
                go_date = a1.date_input("Date", date.today(),
                                        key=f"outgoing_date_{sid}")
                go_cong = a2.text_input("Congregation", key=f"outgoing_cong_{sid}",
                                        placeholder="e.g. Dansoman Beach Ga")
                talk_choices = ["—"] + numbers
                go_talk = a3.selectbox(
                    "Talk", talk_choices, key=f"outgoing_talk_{sid}",
                    format_func=lambda n: "Not specified" if n == "—"
                    else talk_label(n, talk_titles.get(n, "")))
                if st.button("Add date", key=f"add_outgoing_{sid}"):
                    add_outgoing_engagement(sid, go_date, go_cong,
                                            "" if go_talk == "—" else go_talk)
                    st.success("Added.")
                    st.rerun()

    st.divider()
    st.subheader("Approve a speaker")
    candidates = [sid for sid in brothers["id"].tolist() if sid not in approved]
    if not candidates:
        st.caption("Every active brother is already listed above.")
    else:
        pick = st.selectbox("Brother", candidates, format_func=lambda i: names[i],
                            key="outgoing_new_pick")
        if talks:
            chosen_numbers = st.multiselect(
                "Talks he has prepared", [n for n, _ in talks],
                format_func=lambda n: talk_label(n, talk_titles.get(n, "")),
                key="outgoing_new_talks")
        else:
            st.caption("No talks in the list yet — add them in the Talk list "
                       "tab, then come back to attach them.")
            chosen_numbers = []
        if st.button("Approve as outgoing speaker", type="primary"):
            set_outgoing_speaker(pick, chosen_numbers)
            st.success(f"{names[pick]} added.")
            st.rerun()

    st.divider()
    st.subheader("Outgoing speakers letter")
    st.caption("A letter for another congregation, listing our approved "
               "outgoing speakers and the talks they have ready.")
    all_names = dict(zip(students_df["id"], students_df["name"]))
    speakers = sorted(
        ((all_names[sid], [(n, talk_titles.get(n, "")) for n in numbers])
         for sid, numbers in approved.items() if sid in all_names),
        key=lambda s: s[0].lower())
    if not speakers:
        st.info("Approve a speaker above and the letter can be printed.")
        return
    letter = outgoing_speakers_letter_pdf(
        get_setting("congregation", ""), get_setting("hall_address", ""),
        speakers, get_setting("talk_coordinator_signoff", "Bernard Mensah"),
        get_setting("talk_coordinator_phone", ""),
        get_setting("talk_coordinator_email", ""))
    st.download_button(
        "Download outgoing speakers letter", data=letter, icon=":material/mail:",
        file_name=f"outgoing_speakers_{date.today().isoformat()}.pdf",
        mime="application/pdf")


# ----------------------------------------------------------------- checklist
def checklist(schedules_df):
    st.caption("Every talk, one row per number, with a column per year — a "
               "blank cell means it hasn't been given that year, so it's "
               "safe to assign again. Nothing here is ever deleted.")
    n_years = st.number_input("Years to show", min_value=1, max_value=6, value=3,
                              step=1, key="checklist_years")
    years = list(range(date.today().year - int(n_years) + 1, date.today().year + 1))
    matrix_rows = talk_matrix_rows(schedules_df, years)
    if not matrix_rows:
        st.info("No talks in the list yet — add them in the Talk list tab.")
        return

    def cell_text(entries):
        return "; ".join(f"{fmt_date(d, short=True)} — {who}" for d, who in entries)

    table = pd.DataFrame([
        {"No.": r["number"], "Title": r["title"],
         **{str(y): cell_text(r["years"].get(y) or []) for y in years}}
        for r in matrix_rows
    ])
    st.dataframe(table, width="stretch", hide_index=True)
    span = str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}"
    st.download_button(
        f"Download checklist ({span})", icon=":material/checklist:",
        data=talk_checklist_pdf(matrix_rows, get_setting("congregation", ""), years),
        file_name=f"talk_checklist_{years[0]}_{years[-1]}.pdf",
        mime="application/pdf")


# ----------------------------------------------------------------- talk list
def talk_list():
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


# ------------------------------------------------------------ letter details
def letter_details():
    st.caption("Printed on the invitation letter and the outgoing speakers "
               "letter.")
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
        help="Signs every letter. Update this here whenever the Talk "
             "Coordinator changes.")
    c3, c4 = st.columns(2)
    phone = c3.text_input(
        "Talk Coordinator phone", get_setting("talk_coordinator_phone", ""),
        placeholder="e.g. 055 307 8753",
        help="For the other congregation to reach out with questions.")
    email = c4.text_input(
        "Talk Coordinator email", get_setting("talk_coordinator_email", ""),
        placeholder="e.g. niio@jwpub.org")
    if st.button("Save letter details", type="primary"):
        set_setting("meeting_time", meeting_time)
        set_setting("hall_address", hall_address)
        set_setting("talk_coordinator_signoff", signoff)
        set_setting("talk_coordinator_phone", phone)
        set_setting("talk_coordinator_email", email)
        st.success("Saved.")
