# -*- coding: utf-8 -*-
"""Database behaviour: upgrades, participants, backups, reports."""
import json
from datetime import date, timedelta

from conftest import legacy_db


def test_upgrade_from_first_version(fresh_db):
    legacy_db(fresh_db)
    import core
    core.init_db()
    df = core.get_schedules()
    assert len(df) == 3
    assert df["student_id"].notna().all()           # names matched to people
    assert set(df["role"]) == {"Chairman", "Initial Presentation", "Weekend Chairman"}
    kofi = core.get_students().set_index("name").loc["Kofi Mensah"]
    assert "Treasures Talk" in kofi["privilege_list"]  # old "Talk" privilege upgraded


def test_ga_letters_converted_when_enabled(core):
    core.set_setting("ga_convert", "1")
    core.add_student("K3kN)", "Brother", [])
    core.add_student("Naa Ode", "Sister", [])
    names = set(core.get_students()["name"])
    assert {"Kɛkŋɔ", "Naa Ode"} <= names


def test_suspension_and_away(core, people):
    today = date.today()
    core.set_suspension(people["Ama Owusu"], True, (today + timedelta(days=5)).isoformat())
    students = core.get_students()
    assert people["Ama Owusu"] in core.get_suspended(students, today.isoformat())
    later = (today + timedelta(days=6)).isoformat()
    assert people["Ama Owusu"] not in core.get_suspended(students, later)  # lifts itself

    core.set_unavailable(people["Efua Osei"],
                         [(today + timedelta(days=n)).isoformat() for n in (0, 1, 2, 5)])
    assert people["Efua Osei"] in core.get_unavailable(today.isoformat())
    summary = core.away_summary(core.unavailable_dates(people["Efua Osei"]))
    assert summary.count("–") == 1 and "," in summary


def test_family_assistant_and_suggest(core, people):
    students = core.get_students()
    pool = core.assistant_pool(students, people["Kojo Mensah"], set())
    assert people["Esi Mensah"] in pool          # mother may assist her son
    assert people["Ama Owusu"] not in pool       # an unrelated sister may not
    slots = core.apply_aux(core.build_midweek_slots(core.default_midweek_parts()), True)
    away = {people["Kofi Mensah"]}
    picks = core.suggest_assignments(slots, students, away, date.today().isoformat())
    chosen = [p for pair in picks.values() for p in pair if p]
    assert people["Kofi Mensah"] not in chosen
    assert len(chosen) == len(set(chosen))       # nobody twice


def test_backup_round_trip(core, people):
    slots = core.build_midweek_slots(core.default_midweek_parts())
    core.save_schedule("2026-09-16", core.MIDWEEK, slots,
                       {0: (people["Kofi Mensah"], None)},
                       {"heading": "SEPT", "aux": False}, {people["Kofi Mensah"]: "Kofi"})
    backup = json.loads(core.backup_bytes())
    assert len(backup["students"]) == len(people)

    core.delete_schedule("2026-09-16", core.MIDWEEK)
    core.delete_student(people["Yaw Adjei"])
    counts = core.import_all(backup)
    assert counts["students"] == len(people)
    assert len(core.get_schedules()) == len(slots)
    assert core.get_meeting_meta("2026-09-16", core.MIDWEEK)["heading"] == "SEPT"
    actions = set(core.get_log()["action"])
    assert {"Schedule saved", "Data restored"} <= actions


def test_report_counts_parts_and_assisting(core, people):
    from reports import build_report
    slots = core.build_midweek_slots(core.default_midweek_parts())
    ip = next(i for i, s in enumerate(slots) if s["role"] == "Initial Presentation")
    core.save_schedule(date.today().isoformat(), core.MIDWEEK, slots,
                       {ip: (people["Ama Owusu"], people["Efua Osei"])}, {}, {})
    report = build_report(core.get_students(), core.get_schedules(),
                          "2000-01-01", "2999-01-01").set_index("Name")
    assert report.loc["Ama Owusu", "Parts"] == 1
    assert report.loc["Efua Osei", "Assisting"] == 1
    assert report.loc["Yaw Adjei", "Total"] == 0
