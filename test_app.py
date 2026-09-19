# -*- coding: utf-8 -*-
"""The app itself, driven through Streamlit's test runner."""
from datetime import date, timedelta

from streamlit.testing.v1 import AppTest

from conftest import APP, button, run

TODAY = date.today().isoformat()


def app(page=None, **state):
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    if page:
        at.session_state["menu"] = page
    for k, v in state.items():
        at.session_state[k] = v
    return run(at)


def slot_key(ns, hall, role, no, title, kind="student"):
    return f"{ns}|{hall}|{role}|{no}|{title}|{kind}"


def test_every_page_opens(people):
    at = app()
    for page in ["Manage Participants", "Schedule", "View Schedules", "Upload PDF Brochure",
                 "Export", "Month", "Reports", "Admin", "Dashboard"]:
        at.session_state["menu"] = page
        run(at)


def test_create_midweek_with_aux_and_family_assistant(people):
    at = app("Schedule", schedule_mode="Create new")
    ns = f"{TODAY}|Midweek Meeting|default"
    kojo = slot_key(ns, "main_hall", "Initial Presentation", 4, "Initial Presentation")
    # a field-ministry part is filtered to one category, so choose it first —
    # the dropdown never offers someone the filter has excluded
    at.session_state[kojo.replace("|student", "|cat")] = "Brother"
    run(at)
    at.session_state[kojo] = people["Kojo Mensah"]
    run(at)
    assistant = next(s for s in at.selectbox if s.key == kojo.replace("student", "assistant"))
    assert "(family)" not in assistant.options[1]
    assert "· family" in assistant.options[1]            # family listed first
    at.session_state[kojo.replace("student", "assistant")] = people["Esi Mensah"]
    aux_key = slot_key(ns, "aux_1", "Initial Presentation", 4, "Initial Presentation")
    at.session_state[aux_key.replace("|student", "|cat")] = "Sister"
    run(at)
    at.session_state[aux_key] = people["Ama Owusu"]
    run(at)
    button(at, "Save schedule").click()
    run(at)
    assert any("Saved Midweek Meeting" in s.value for s in at.success)
    assert not any("different categories" in w.value for w in at.warning)
    rows = __import__("core").get_schedules()
    assert set(rows["hall"]) == {"main_hall", "aux_1"}


def test_suspended_and_away_people_are_not_offered(people, core):
    core.set_suspension(people["Nii Tetteh"], True)
    core.set_unavailable(people["Kofi Mensah"], [TODAY])
    at = app("Schedule", schedule_mode="Create new")
    chairman = next(s for s in at.selectbox if s.label == "Chairman")
    assert not any("Nii" in o or "Kofi" in o for o in chairman.options)
    button(at, "Suggest").click()
    run(at)
    values = [s.value for s in at.selectbox]
    assert people["Nii Tetteh"] not in values and people["Kofi Mensah"] not in values


def test_weekend_chairman_visitor_and_talk(people):
    at = app("Schedule", schedule_mode="Create new", new_meeting_type="Weekend Meeting")
    chairman = next(s for s in at.selectbox if s.label == "Chairman")
    assert any("Yaw" in o for o in chairman.options)
    assert not any("Kofi" in o for o in chairman.options)   # midweek-only chairman
    next(c for c in at.checkbox if "Visiting speaker" in c.label).check()
    run(at)
    next(t for t in at.text_input if "Public Talk" in t.label).set_value("Bro. Addo — Osu")
    next(t for t in at.text_input if t.label == "Talk no.").set_value("12")
    next(t for t in at.text_input if t.label == "Talk title").set_value("A Good Title")
    run(at)
    button(at, "Save schedule").click()
    run(at)
    at.session_state["menu"] = "View Schedules"
    run(at)
    table = at.dataframe[0].value
    assert "Bro. Addo — Osu" in table["Assigned to"].tolist()
    assert any("No. 12" in m.value for m in at.markdown)


def test_workbook_week_follows_the_date(people, core, ga_workbook):
    weeks, _, _ = core.parse_brochure(ga_workbook)
    core.save_workbook(core.assign_dates(weeks, date(2026, 9, 7)), "ga.pdf")
    at = app("Schedule", schedule_mode="Create new")
    seen = {}
    for d in (date(2026, 9, 10), date(2026, 9, 17), date(2026, 10, 1)):
        at.date_input(key="new_meeting_date").set_value(d)
        run(at)
        week = [s.value for s in at.selectbox if s.label == "Workbook week"][0]
        first = next(s.label for s in at.selectbox if s.label.startswith("1."))
        seen[d.day] = (week, first)
    assert seen[10] == ("SƐPTƐMBA 7–13", "1. A Treasures Talk (10 min)")
    assert seen[17] == ("SƐPTƐMBA 14–20", "1. B Treasures Talk (10 min)")
    assert seen[1][0] is None                                   # no silent fallback
    assert any("No workbook week covers" in w.value for w in at.warning)


def test_saved_schedule_mismatch_is_flagged(people, core, english_workbook):
    slots = core.build_midweek_slots(core.default_midweek_parts())
    core.save_schedule("2026-09-16", core.MIDWEEK, slots, {}, {}, {})
    weeks, _, _ = core.parse_brochure(english_workbook)
    core.save_workbook(core.assign_dates(weeks, date(2026, 9, 14)), "en.pdf")
    at = app("Schedule", schedule_mode="Edit saved")
    assert any("8 numbered part(s)" in w.value for w in at.warning)
    next(c for c in at.checkbox if c.label.startswith("Use parts")).check()
    run(at)
    numbered = [s.label for s in at.selectbox if s.label[:2].strip(". ").isdigit()]
    assert len({n.split(".")[0] for n in numbered}) == 10


def test_month_view_create_button_and_downloads(people, core, english_workbook):
    weeks, _, _ = core.parse_brochure(english_workbook)
    core.save_workbook(core.assign_dates(weeks, date(2026, 9, 14)), "en.pdf")
    slots = core.build_midweek_slots(core.default_midweek_parts())
    ip = next(i for i, s in enumerate(slots) if s["role"] == "Initial Presentation")
    core.save_schedule("2026-09-16", core.MIDWEEK, slots,
                       {ip: (people["Ama Owusu"], people["Efua Osei"])}, {}, {})
    at = app("Month", month_view_month="2026-09")
    table = at.dataframe[0].value
    assert "not created yet" in " ".join(table["Heading"])
    assert len(at.get("download_button")) == 2
    button(at, "Create 23 Sep").click()
    run(at)
    assert at.session_state["menu"] == "Schedule"
    assert at.date_input(key="new_meeting_date").value == date(2026, 9, 23)


def test_reports_page_lists_people_without_parts(people):
    at = app("Reports")
    assert any("no assignment" in w.value for w in at.warning)


def test_login_required_when_password_set(people):
    at = AppTest.from_file(APP, default_timeout=90)
    at.secrets["auth"] = {"password": "open-sesame"}
    run(at)
    assert not any(b.label == "Month overview" for b in at.button)
    at.text_input[0].set_value("Xan")
    at.text_input[1].set_value("wrong")
    at.button[0].click()
    run(at)
    assert any("Wrong" in e.value for e in at.error)
    at.text_input[1].set_value("open-sesame")
    at.button[0].click()
    run(at)
    assert any(b.label == "Month overview" for b in at.button)
    import core
    assert "Xan" in set(core.get_log()["user"])


def test_sheets_export_is_manual_and_data_survives_a_restart(people, core, fake_sheet,
                                                             fresh_db):
    at = app("Manage Participants")
    next(t for t in at.text_input if t.label == "Full name").set_value("Abena Asare")
    run(at)
    button(at, "Add participant").click()
    run(at)
    # nothing is sent to Google until someone asks for it
    assert "students" not in fake_sheet.sheets

    at.session_state["menu"] = "Admin"
    run(at)
    button(at, "Copy everything to Google Sheets now").click()
    run(at)
    names = [r[1] for r in fake_sheet.sheets["students"].values[1:]]
    assert "Abena Asare" in names

    # an unchanged table isn't sent again (the button forces a full copy, so
    # check the digest short-circuit on a plain export)
    calls = fake_sheet.sheets["schedules"].calls
    core.push()
    assert fake_sheet.sheets["schedules"].calls == calls

    # the app restarting no longer loses anything, so there is nothing to restore
    at2 = AppTest.from_file(APP, default_timeout=90)
    run(at2)
    kept = set(core.get_students()["name"])
    assert "Abena Asare" in kept and "Kofi Mensah" in kept
    assert "Restored from Google Sheets" not in set(core.get_log()["action"])


def test_loading_back_from_sheets_keeps_ids_usable(people, core, fake_sheet):
    """Rows come back with their own ids, so the id sequence must move past them."""
    core.push(force=True)
    core.delete_student(people["Yaw Adjei"])
    core.import_all(core.pull())
    assert "Yaw Adjei" in set(core.get_students()["name"])
    core.add_student("Naa Dedei", "Sister", ["Initial Presentation"])   # must not clash
    df = core.get_students()
    assert "Naa Dedei" in set(df["name"])
    assert df["id"].is_unique


def test_admin_backup_restore(people, core):
    backup = core.backup_bytes()
    core.delete_student(people["Yaw Adjei"])
    at = app("Admin")
    # the uploader can't be driven by the test runner, so restore directly
    core.import_all(__import__("json").loads(backup))
    run(at)
    assert "Yaw Adjei" in set(core.get_students()["name"])
    assert any(b.label.startswith("Download full backup")
               for b in at.get("download_button"))


def test_home_leads_with_the_next_meeting(people, core):
    soon = (date.today() + timedelta(days=2)).isoformat()
    slots = core.build_midweek_slots(core.default_midweek_parts())
    ip = next(i for i, s in enumerate(slots) if s["role"] == "Initial Presentation")
    core.save_schedule(soon, core.MIDWEEK, slots,
                       {0: (people["Kofi Mensah"], None),
                        ip: (people["Ama Owusu"], None)},
                       {"heading": "SEPTEMBER 14–20"}, {})
    at = app()
    page = " ".join(m.value for m in at.markdown)
    assert "Treasures From God’s Word" in page and "of" in page
    assert "slots open" in page
    button(at, "Fill open slots").click()
    run(at)
    assert at.session_state["menu"] == "Schedule"
    assert at.selectbox(key="edit_meeting").value == (soon, core.MIDWEEK)


def test_home_empty_states(core):
    at = app()
    assert any(b.label == "Add participants" for b in at.button)
    core.add_student("Kofi Mensah", "Brother", ["Chairman"])
    run(at)
    assert any("No meetings scheduled yet" in m.value for m in at.markdown)


def test_sidebar_navigation(people):
    at = app()
    next(b for b in at.button if b.label == "Reports").click()
    run(at)
    assert at.session_state["menu"] == "Reports"
    active = [b for b in at.button if b.key and b.key.startswith("nav_")
              and b.proto.type == "primary"]
    assert [b.label for b in active] == ["Reports"]


def test_a_past_meeting_day_is_not_offered(core, english_workbook, monkeypatch):
    """On a Thursday, this week's Wednesday meeting has already happened."""
    import datetime as dt

    import dashboard

    weeks, _, _ = core.parse_brochure(english_workbook)
    core.save_workbook(core.assign_dates(weeks, dt.date(2026, 9, 14)), "en.pdf")
    core.set_setting("midweek_day", "Wednesday")
    schedules = core.get_schedules()

    class Thursday(dt.date):
        @classmethod
        def today(cls):
            return cls(2026, 9, 17)          # the day after that week's meeting

    monkeypatch.setattr(dashboard, "date", Thursday)
    label, when = dashboard.next_unscheduled_week(schedules)
    assert when == dt.date(2026, 9, 23)      # the following week, not the 16th
    assert when > Thursday.today()
    assert label == "SEPTEMBER 21–27"

    class Tuesday(Thursday):
        @classmethod
        def today(cls):
            return cls(2026, 9, 15)          # the day before it

    monkeypatch.setattr(dashboard, "date", Tuesday)
    _, when = dashboard.next_unscheduled_week(schedules)
    assert when == dt.date(2026, 9, 16)      # still offered while it is ahead


def test_schedules_download_as_two_separate_sheets(people, core):
    """Midweek and weekend print separately — they are different documents for
    different people."""
    import core as c

    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    mid = c.build_midweek_slots(c.default_midweek_parts())
    core.save_schedule("2026-09-16", c.MIDWEEK, mid,
                       {0: (people["Kofi Mensah"], None)}, {}, names)
    wknd = c.default_weekend_slots()
    core.save_schedule("2026-09-20", c.WEEKEND, wknd,
                       {0: (people["Yaw Adjei"], None)}, {}, names)

    midweek, weekend = c.split_by_type(
        [("2026-09-20", c.WEEKEND), ("2026-09-16", c.MIDWEEK)])
    assert midweek == [("2026-09-16", c.MIDWEEK)]
    assert weekend == [("2026-09-20", c.WEEKEND)]

    at = app("Month", month_view_month="2026-09")
    labels = [b.label for b in at.get("download_button")]
    assert any(l.startswith("Midweek schedule") for l in labels), labels
    assert any(l.startswith("Weekend schedule") for l in labels), labels
    assert not any("Schedule PDF" in l for l in labels)      # no combined file


def test_ministry_lists_are_one_category_at_a_time(people, core):
    """A field-ministry part goes to a sister or to a brother. The list used to
    hold both; now a category is chosen first and only those names appear."""
    at = app("Schedule", schedule_mode="Create new")
    ns = f"{TODAY}|Midweek Meeting|default"
    key = slot_key(ns, "main_hall", "Initial Presentation", 4, "Initial Presentation")

    at.session_state[key.replace("|student", "|cat")] = "Sister"
    run(at)
    box = next(s for s in at.selectbox if s.key == key)
    offered = [o for o in box.options if o != "— Unassigned —"]
    assert offered and all("Mensah" not in o or "Esi" in o for o in offered)
    assert not any("Kojo" in o for o in offered)        # a brother
    assert any("Ama Owusu" in o for o in offered)       # a sister

    at.session_state[key.replace("|student", "|cat")] = "Brother"
    run(at)
    box = next(s for s in at.selectbox if s.key == key)
    offered = [o for o in box.options if o != "— Unassigned —"]
    assert any("Kojo" in o for o in offered)
    assert not any("Ama Owusu" in o for o in offered)

    # a brothers-only part has no category control and no sisters in it
    reading = slot_key(ns, "main_hall", "Bible Reading", 3, "Bible Reading")
    box = next(s for s in at.selectbox if s.key == reading)
    assert not any("Ama Owusu" in o for o in box.options)


def test_dropdowns_show_how_long_ago_and_what_it_was(people, core):
    """Each name carries a colour for how long they have waited and what they
    last did."""
    import core as c

    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    slots = c.build_midweek_slots(c.default_midweek_parts())
    reading = next(i for i, s in enumerate(slots) if s["role"] == "Bible Reading")
    recent = (date.today() - timedelta(days=3)).isoformat()
    core.save_schedule(recent, c.MIDWEEK, slots,
                       {reading: (people["Nii Tetteh"], None)}, {}, names)

    at = app("Schedule", schedule_mode="Create new")
    ns = f"{TODAY}|Midweek Meeting|default"
    key = slot_key(ns, "main_hall", "Bible Reading", 3, "Bible Reading")
    box = next(s for s in at.selectbox if s.key == key)
    nii = next(o for o in box.options if "Nii Tetteh" in o)
    assert nii.startswith("🔴")                       # three days ago
    # for the very same part the wording says so rather than repeating it
    assert "this same part" in nii

    kojo = next(o for o in box.options if "Kojo" in o)
    assert kojo.startswith("⚫") and "no parts yet" in kojo

    # on a different part, the label names what they last did
    chairman = slot_key(ns, "main_hall", "Chairman", None, "Chairman")
    box = next(s for s in at.selectbox if s.key == chairman)
    nii = next(o for o in box.options if "Nii Tetteh" in o)
    assert nii.startswith("🔴") and "Bible Reading" in nii
