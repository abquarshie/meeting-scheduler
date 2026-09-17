# -*- coding: utf-8 -*-
"""Schedule page."""
from core import *  # noqa: F401,F403


def render(students_df, t, selected_lang, aux_default):
    page_header(tr("h_schedule"), tr("sub_schedule"))
    schedules_df = get_schedules()
    meetings = saved_meetings(schedules_df)

    mode = st.radio("Mode", ["Create new", "Edit saved"], horizontal=True,
                    key="schedule_mode")
    if mode == "Edit saved":
        if not meetings:
            st.info("No saved schedules yet.")
            st.stop()
        if st.session_state.get("edit_meeting") not in meetings:
            st.session_state.pop("edit_meeting", None)
        meeting_date, meeting_type = st.selectbox(
            "Saved schedule", meetings, format_func=meeting_label, key="edit_meeting")
    else:
        c1, c2 = st.columns(2)
        st.session_state.setdefault("new_meeting_type", MIDWEEK)
        st.session_state.setdefault("new_meeting_date", date.today())
        meeting_type = c1.selectbox("Meeting type", MEETING_TYPES, key="new_meeting_type")
        meeting_date = c2.date_input("Meeting date", key="new_meeting_date").isoformat()

    saved_slots, saved_picks, saved_visitors = load_schedule(
        meeting_date, meeting_type, schedules_df)
    meta = get_meeting_meta(meeting_date, meeting_type)
    if saved_slots and mode == "Create new":
        st.info("A schedule is already saved for this date. It's loaded below, "
                "and saving will replace it.")

    brochure, brochure_file = load_workbook()
    source = "saved" if saved_slots else "default"
    slots = saved_slots or (
        build_midweek_slots(default_midweek_parts())
        if meeting_type == MIDWEEK else default_weekend_slots())

    if meeting_type == MIDWEEK and brochure:
        labels = list(brochure)
        matched = week_for_date(brochure, meeting_date)
        if not matched:
            st.warning(
                f"No workbook week covers {fmt_date(meeting_date)}. Check the week dates "
                "under Upload Workbook PDF, or pick the week yourself below."
            )
        wb_parts = brochure[matched]["parts"] if matched else []
        saved_numbered = [(s_["part_no"], s_["title"]) for s_ in saved_slots
                          if s_.get("part_no") and s_.get("hall", MAIN_HALL) == MAIN_HALL]
        wb_numbered = [(p_["part_no"], p_["title"]) for p_ in wb_parts]
        differs = bool(saved_slots and matched and saved_numbered != wb_numbered)
        if differs:
            st.warning(
                f"The saved schedule has {len(saved_numbered)} numbered part(s), but the "
                f"workbook week **{matched}** has {len(wb_numbered)}, or the titles differ. "
                "Tick the box below to switch to the workbook parts; names carry over "
                "where the part number and role match."
            )
        use_brochure = st.checkbox(
            "Use parts from the uploaded workbook", value=not saved_slots,
            help="Names already picked carry over when the part number and role match.",
        )
        week = matched
        if use_brochure:
            week = st.selectbox(
                "Workbook week", labels,
                index=labels.index(matched) if matched else None,
                format_func=lambda l: f"{l}  ·  {week_dates_text(brochure[l])}",
                placeholder="Choose the workbook week",
                key=f"wbweek|{meeting_date}|{matched}",
                help="Chosen automatically from the meeting date when it matches.",
            )
        if use_brochure and week:
            slots = build_midweek_slots(brochure[week]["parts"])
            source = f"brochure:{week}"
            songs = brochure[week].get("songs", [])
            if not saved_slots:
                meta = {
                    **meta,
                    "heading": week,
                    "opening_song": f"Song {songs[0]}" if len(songs) > 0 else "",
                    "middle_song": f"Song {songs[1]}" if len(songs) > 1 else "",
                    "closing_song": f"Song {songs[2]}" if len(songs) > 2 else "",
                }

        if week:
            wk = brochure[week]
            with st.expander(f"Cross-check with the workbook: {week}, "
                             f"{week_dates_text(wk)} ({len(wk['parts'])} parts)",
                             icon=":material/fact_check:",
                             expanded=differs):
                if wk.get("gaps"):
                    st.error("Part number(s) not found in the workbook text: "
                             + ", ".join(map(str, wk["gaps"]))
                             + ". Add them under Upload Workbook PDF → Review week.")
                st.dataframe(pd.DataFrame(parts_summary(wk["parts"])),
                             width="stretch", hide_index=True)
                st.text_area("Workbook text for this week", wk.get("text", ""),
                             height=260, key=f"wbtext|{meeting_date}|{week}")
    elif meeting_type == MIDWEEK:
        st.caption("Using the standard 8-part list. Upload the workbook PDF to get "
                   "this week's real part numbers and titles.")

    aux_on = False
    if meeting_type == MIDWEEK:
        saved_aux = meta.get("aux")
        aux_on = st.checkbox(
            "Auxiliary classroom this week",
            value=bool(saved_aux) if saved_aux is not None else aux_default,
            key=f"{meeting_date}|{meeting_type}|aux",
            help="Adds a counselor and a second student (and assistant) for the "
                 "Bible reading and each field-ministry part.",
        )
    slots = apply_aux(slots, aux_on)

    active = students_df[students_df["active"] == 1]
    if active.empty:
        st.warning("Add participants under 'Manage Participants' first.")
        st.stop()

    c_show, c_suggest = st.columns([3, 1])
    show_all = c_show.checkbox("Show everyone in every list (ignore privileges and category)")
    last_dates = last_assignment_dates(meeting_date)
    away = get_unavailable(meeting_date)
    suspended = get_suspended(students_df, meeting_date)
    blocked = away | suspended  # never offered for new picks
    categories = dict(zip(students_df["id"], students_df["gender"]))
    families = dict(zip(students_df["id"], students_df["family"]))
    names = dict(zip(students_df["id"], students_df["name"]))
    if away:
        st.caption("Away this date: "
                   + ", ".join(sorted(names[p] for p in away if p in names)))
    if suspended:
        st.caption("Suspended (not offered): "
                   + ", ".join(sorted(names[p] for p in suspended if p in names)))

    sugg_key = f"suggest|{meeting_date}|{meeting_type}|{source}"
    if c_suggest.button(tr("suggest"), icon=":material/auto_awesome:", width="stretch",
                        help="Fill empty slots with whoever has waited longest for each part."):
        st.session_state[sugg_key] = suggest_assignments(
            slots, students_df, blocked, meeting_date)
    suggested = st.session_state.get(sugg_key, {})

    ns = f"{meeting_date}|{meeting_type}|{source}"
    with st.expander("Meeting details (used on the S-140)", expanded=False):
        m1, m2 = st.columns(2)
        meta_in = {
            "heading": m1.text_input("Heading", meta.get("heading", ""), key=f"{ns}|heading"),
            "opening_song": m2.text_input("Opening song", meta.get("opening_song", ""),
                                          key=f"{ns}|song1"),
            "middle_song": m1.text_input("Middle song", meta.get("middle_song", ""),
                                         key=f"{ns}|song2"),
            "closing_song": m2.text_input("Closing song", meta.get("closing_song", ""),
                                          key=f"{ns}|song3"),
            "aux": aux_on,
        }

    talk_in = {"talk_number": meta.get("talk_number", ""),
               "talk_title": meta.get("talk_title", "")}

    def talk_inputs():
        with st.container(border=True):
            st.markdown("**Public talk**")
            t1, t2 = st.columns([1, 4])
            talk_in["talk_number"] = nfc(t1.text_input(
                "Talk no.", talk_in["talk_number"], key=f"{ns}|talkno",
                placeholder="e.g. 12"))
            talk_in["talk_title"] = apply_ga_substitutes(nfc(t2.text_input(
                "Talk title", talk_in["talk_title"], key=f"{ns}|talktitle",
                placeholder="Title of the public talk")))

    picks = {}

    def render_slot(i, slot):
        pre_sid, pre_aid = saved_picks.get(slot_match_key(slot), (None, None))
        if i in suggested:
            pre_sid, pre_aid = suggested[i]
        wkey = f"{ns}|{slot['hall']}|{slot['role']}|{slot['part_no']}|{slot['title']}"
        text = slot_label(slot)
        if aux_on and slot["student_part"] and slot["hall"] == MAIN_HALL:
            text += " · Main hall"

        # a visiting public-talk speaker is typed by hand, not chosen from the list
        if slot.get("allow_visitor"):
            vkey = f"{wkey}|visitor"
            saved_visitor = saved_visitors.get(slot_match_key(slot), "")
            is_visitor = st.checkbox("Visiting speaker (another congregation)",
                                     value=bool(saved_visitor), key=f"{wkey}|isvis")
            if is_visitor:
                vis = st.text_input(text, saved_visitor, key=vkey,
                                    placeholder="Name — Congregation")
                picks[i] = (None, None)
                picks[i + 10000] = apply_ga_substitutes(nfc(vis))
                talk_inputs()
                return

        role_dates = last_role_dates(slot["role"])
        options = ordered_options(
            eligible_ids(slot["role"], students_df, show_all, away, suspended),
            role_dates, keep=pre_sid)
        if pre_sid not in options:
            pre_sid = None
        label = person_label_factory(students_df, last_dates, away, role_dates,
                                     suspended=suspended)
        cols = st.columns(2) if slot["needs_assistant"] else [st.container()]
        sid = cols[0].selectbox(
            text, options, index=options.index(pre_sid),
            format_func=label, key=f"{wkey}|student",
        )
        aid = None
        if slot["needs_assistant"]:
            pool = assistant_pool(students_df, sid, blocked, show_all)
            a_options = ordered_options(pool, last_dates, keep=pre_aid)
            # family members first (sort is stable, so rotation order is kept)
            a_options = [None] + sorted(
                a_options[1:], key=lambda p: not same_family(families, p, sid))
            if pre_aid not in a_options:
                pre_aid = None
            a_label = person_label_factory(students_df, last_dates, away, family_of=sid,
                                           suspended=suspended)
            aid = cols[1].selectbox(
                "Assistant", a_options, index=a_options.index(pre_aid),
                format_func=a_label, key=f"{wkey}|assistant",
            )
        picks[i] = (sid, aid)
        if slot["role"] == "Public Talk":
            talk_inputs()

    # one bordered block per workbook section; single parts sit two to a row
    groups = []
    for i, slot in enumerate(slots):
        if not groups or groups[-1][0] != slot["section"]:
            groups.append((slot["section"], []))
        groups[-1][1].append((i, slot))
    for section, members in groups:
        section_heading(section)
        with st.container(border=True):
            pending = None
            for i, slot in members:
                wide = slot["needs_assistant"] or slot.get("allow_visitor") \
                    or slot["role"] == "Public Talk"
                if wide:
                    pending = None
                    render_slot(i, slot)
                    continue
                if pending is None:
                    left, right = st.columns(2)
                    with left:
                        render_slot(i, slot)
                    pending = right
                else:
                    with pending:
                        render_slot(i, slot)
                    pending = None

    st.markdown("---")
    b1, b2 = st.columns([1, 1])
    if b1.button(tr("save_schedule"), icon=":material/save:", type="primary", width="stretch"):
        errors, warnings = [], []
        usage = {}
        for i, val in picks.items():
            if i >= 10000:  # visitor name entries, not (sid, aid)
                continue
            sid, aid = val
            if sid is not None and sid == aid:
                errors.append(f"{names[sid]} is both student and assistant on "
                              f"'{slot_label(slots[i])}'.")
            for pid in (sid, aid):
                if pid is not None:
                    usage.setdefault(pid, []).append(slot_label(slots[i]))
            if (sid and aid and categories.get(sid) != categories.get(aid)
                    and not same_family(families, sid, aid)):
                warnings.append(f"'{slot_label(slots[i])}': student and assistant "
                                "are in different categories and not family.")
        for pid, parts in usage.items():
            if len(parts) > 1:
                warnings.append(f"{names[pid]} has {len(parts)} parts: {', '.join(parts)}.")
        for pid in set(usage) & suspended:
            warnings.append(f"{names[pid]} is suspended but still assigned: "
                            f"{', '.join(usage[pid])}.")
        other_type = WEEKEND if meeting_type == MIDWEEK else MIDWEEK
        _, other_picks, _ = load_schedule(meeting_date, other_type, schedules_df)
        other_people = {p for pair in other_picks.values() for p in pair if p}
        for pid in set(usage) & other_people:
            warnings.append(f"{names[pid]} also has a part in the {other_type} on this date.")

        if errors:
            for e in errors:
                st.error(e, icon=":material/error:")
        else:
            meta_in.update(talk_in)
            save_schedule(meeting_date, meeting_type, slots, picks, meta_in, names)
            st.success(f"Saved {meeting_type} for {fmt_date(meeting_date)}.")
            for w in warnings:
                st.warning(f"Check: {w}")

    if saved_slots and b2.button("Delete this schedule", icon=":material/delete:",
                                     width="stretch"):
        st.session_state["confirm_delete"] = (meeting_date, meeting_type)
    if st.session_state.get("confirm_delete") == (meeting_date, meeting_type):
        st.error(f"Delete the {meeting_type} for {fmt_date(meeting_date)}?")
        y, n = st.columns(2)
        if y.button("Yes, delete", type="primary"):
            delete_schedule(meeting_date, meeting_type)
            st.session_state.pop("confirm_delete")
            st.rerun()
        if n.button("Cancel"):
            st.session_state.pop("confirm_delete")
            st.rerun()
