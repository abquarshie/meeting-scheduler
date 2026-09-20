# -*- coding: utf-8 -*-
"""Database behaviour: upgrades, participants, backups, reports."""
import json
from datetime import date, timedelta



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


def test_undo_restores_the_previous_save(core, people):
    slots = core.build_midweek_slots(core.default_midweek_parts())
    ip = next(i for i, s in enumerate(slots) if s["role"] == "Initial Presentation")
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))

    assert core.last_snapshot("2026-09-16", core.MIDWEEK) is None
    assert core.undo_last("2026-09-16", core.MIDWEEK) is None      # nothing to undo yet

    core.save_schedule("2026-09-16", core.MIDWEEK, slots,
                       {ip: (people["Ama Owusu"], people["Efua Osei"])},
                       {"heading": "FIRST"}, names)
    core.save_schedule("2026-09-16", core.MIDWEEK, slots,
                       {ip: (people["Esi Mensah"], None)},
                       {"heading": "SECOND"}, names)

    df = core.get_schedules()
    row = df[(df["meeting_date"] == "2026-09-16") & (df["role"] == "Initial Presentation")]
    assert row["person"].iloc[0] == "Esi Mensah"

    snap = core.last_snapshot("2026-09-16", core.MIDWEEK)
    assert snap["reason"] == "before save" and snap["rows"] == len(slots)

    core.undo_last("2026-09-16", core.MIDWEEK)
    df = core.get_schedules()
    row = df[(df["meeting_date"] == "2026-09-16") & (df["role"] == "Initial Presentation")]
    assert row["person"].iloc[0] == "Ama Owusu"                    # the first save is back
    assert row["assistant"].iloc[0] == "Efua Osei"
    assert core.get_meeting_meta("2026-09-16", core.MIDWEEK)["heading"] == "FIRST"

    core.undo_last("2026-09-16", core.MIDWEEK)                     # undo is itself undoable
    df = core.get_schedules()
    row = df[(df["meeting_date"] == "2026-09-16") & (df["role"] == "Initial Presentation")]
    assert row["person"].iloc[0] == "Esi Mensah"
    assert "Save undone" in set(core.get_log()["action"])


def test_undo_after_delete_and_after_a_first_save(core, people):
    slots = core.build_midweek_slots(core.default_midweek_parts())
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    core.save_schedule("2026-09-23", core.MIDWEEK, slots,
                       {0: (people["Kofi Mensah"], None)}, {}, names)

    core.delete_schedule("2026-09-23", core.MIDWEEK)
    assert core.get_schedules().empty
    core.undo_last("2026-09-23", core.MIDWEEK)
    assert len(core.get_schedules()) == len(slots)                 # delete is undoable

    # undoing back past the very first save leaves nothing, not a half-saved meeting
    for _ in range(4):
        core.undo_last("2026-09-23", core.MIDWEEK)
    core.undo_last("2026-09-23", core.MIDWEEK)
    rows = core.get_schedules()
    assert rows.empty or len(rows) == len(slots)


def test_nested_writes_share_one_connection(core, people):
    """save_schedule() logs a change while holding a connection. If that took a
    second one from the pool, concurrent saves would deadlock."""
    import db
    slots = core.build_midweek_slots(core.default_midweek_parts())
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    with db.get_conn() as outer:
        with db.get_conn() as inner:
            assert inner is outer
    core.save_schedule("2026-10-07", core.MIDWEEK, slots,
                       {0: (people["Kofi Mensah"], None)}, {}, names)
    assert "Schedule saved" in set(core.get_log()["action"])


def test_writes_from_several_sessions_at_once(core):
    """Two people editing at the same time is the case SQLite on a shared
    filesystem handled badly."""
    import threading
    errors = []

    def add(n):
        try:
            for i in range(10):
                core.add_student(f"Tester {n}-{i}", "Sister", ["Initial Presentation"])
        except Exception as exc:                      # pragma: no cover - failure path
            errors.append(repr(exc))

    threads = [threading.Thread(target=add, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    df = core.get_students()
    assert len(df) == 40 and df["id"].is_unique


def test_survives_the_database_dropping_connections(core):
    """Neon suspends its compute when idle and terminates open connections.
    The pool must notice before handing one out, or the next page load dies
    with AdminShutdown."""
    import os

    import psycopg

    core.add_student("Kofi Mensah", "Brother", ["Chairman"])
    assert len(core.get_students()) == 1

    def kill_backends():
        dsn = os.environ["MEETING_DSN"]
        with psycopg.connect(dsn, autocommit=True) as raw:
            raw.execute("""SELECT pg_terminate_backend(pid) FROM pg_stat_activity
                            WHERE pid <> pg_backend_pid()
                              AND datname = current_database()""")

    for n in range(3):
        kill_backends()
        core.add_student(f"Person {n}", "Sister", ["Initial Presentation"])

    assert len(core.get_students()) == 4
    # reads recover too, not just writes
    kill_backends()
    assert core.get_setting("nothing", "default") == "default"

    # the exact path that crashed in production: sign-in writes the change log
    # as the first query after the database has been idle
    for n in range(3):
        kill_backends()
        core.log_change("Signed in", f"Tester {n}")
    assert len(core.get_log()) >= 3


# --------------------------------------------------------------- caches
# Four caches sit between the app and the database (schema setup, settings,
# workbook, role dates), each cleared by hand on write. Manual invalidation is
# where stale-data bugs live, and a stale rotation cache is invisible: Suggest
# keeps working, it just stops offering whoever has waited longest.

def _count_queries(monkeypatch):
    """Count database round trips made inside the block."""
    import db
    calls = []
    original = db._Conn.execute

    def spy(self, sql, params=()):
        calls.append(" ".join(str(sql).split())[:60])
        return original(self, sql, params)

    monkeypatch.setattr(db._Conn, "execute", spy)
    return calls


def test_settings_cache_serves_repeats_and_clears_on_write(core, monkeypatch):
    core.set_setting("midweek_day", "Wednesday")
    assert core.get_setting("midweek_day") == "Wednesday"

    calls = _count_queries(monkeypatch)
    for _ in range(10):
        core.get_setting("midweek_day")
    assert calls == [], "settings should be served from cache, not re-queried"

    core.set_setting("midweek_day", "Thursday")
    assert core.get_setting("midweek_day") == "Thursday"
    assert core.get_setting("never_set", "fallback") == "fallback"


def test_role_dates_cache_clears_on_every_schedule_write(core, people):
    """The rotation cache is the dangerous one: if it goes stale the app still
    works, it just stops rotating fairly."""
    slots = core.build_midweek_slots(core.default_midweek_parts())
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    talk = next(i for i, s in enumerate(slots) if s["role"] == "Treasures Talk")

    assert core.last_role_dates("Treasures Talk") == {}

    core.save_schedule("2026-09-16", core.MIDWEEK, slots,
                       {talk: (people["Kofi Mensah"], None)}, {}, names)
    after_save = core.last_role_dates("Treasures Talk")
    assert after_save == {people["Kofi Mensah"]: "2026-09-16"}

    # a later date replaces the earlier one
    core.save_schedule("2026-09-23", core.MIDWEEK, slots,
                       {talk: (people["Kofi Mensah"], None)}, {}, names)
    assert core.last_role_dates("Treasures Talk")[people["Kofi Mensah"]] == "2026-09-23"

    # undo must roll the rotation back too
    core.undo_last("2026-09-23", core.MIDWEEK)
    assert core.last_role_dates("Treasures Talk")[people["Kofi Mensah"]] == "2026-09-16"

    core.delete_schedule("2026-09-16", core.MIDWEEK)
    assert core.last_role_dates("Treasures Talk") == {}


def test_workbook_cache_clears_when_the_workbook_changes(core, english_workbook,
                                                         monkeypatch):
    weeks, _, _ = core.parse_brochure(english_workbook)
    core.save_workbook(core.assign_dates(weeks, date(2026, 9, 14)), "en.pdf")
    stored, name = core.load_workbook()
    assert name == "en.pdf" and len(stored) == 2

    calls = _count_queries(monkeypatch)
    for _ in range(5):
        core.load_workbook()
    assert calls == [], "the workbook should be read once per run"

    core.save_workbook({}, "")
    assert core.load_workbook() == ({}, "")


def test_restoring_a_backup_clears_the_caches(core, people):
    """import_all replaces every table, so anything cached is stale."""
    slots = core.build_midweek_slots(core.default_midweek_parts())
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    talk = next(i for i, s in enumerate(slots) if s["role"] == "Treasures Talk")
    core.set_setting("congregation", "BEFORE")
    backup = json.loads(core.backup_bytes())

    core.save_schedule("2026-09-16", core.MIDWEEK, slots,
                       {talk: (people["Kofi Mensah"], None)}, {}, names)
    core.set_setting("congregation", "AFTER")
    assert core.get_setting("congregation") == "AFTER"
    assert core.last_role_dates("Treasures Talk")

    core.import_all(backup)
    assert core.get_setting("congregation") == "BEFORE"
    assert core.last_role_dates("Treasures Talk") == {}


def test_backup_reminder_tracks_the_last_backup(core, people):
    """The backup file is the only second copy now, and taking one is a button
    somebody has to remember to press."""
    from datetime import date, timedelta

    overdue, days = core.backup_overdue()
    assert overdue and days is None                # never taken

    core.backup_bytes()                            # downloading one records it
    overdue, days = core.backup_overdue()
    assert not overdue and days == 0

    core.set_setting("last_export", (date.today() - timedelta(days=13)).isoformat())
    assert core.backup_overdue() == (False, 13)
    core.set_setting("last_export", (date.today() - timedelta(days=14)).isoformat())
    assert core.backup_overdue() == (True, 14)

    core.set_setting("last_export", "not a date")
    assert core.backup_overdue()[0]                # unreadable means remind

def test_migrations_run_again_when_the_schema_changes(core, monkeypatch):
    """Streamlit reruns the script on a code push without restarting the
    process, so a schema cache keyed only on the database name survives the
    deploy and the new migration never runs. This is the failure that shipped:
    the app queried a column it had never added."""
    import db

    db.ensure_db()
    first = db.schema_fingerprint()

    # a column added by a later version, as it would look before that deploy
    with db.get_conn() as conn:
        conn.execute("ALTER TABLE meetings DROP COLUMN IF EXISTS aux_group")
    with db.get_conn() as conn:
        cols = db.table_columns(conn, "meetings")
    assert "aux_group" not in cols

    # same code: the cache legitimately skips the work
    db.ensure_db()
    with db.get_conn() as conn:
        assert "aux_group" not in db.table_columns(conn, "meetings")

    # code changed: the fingerprint moves and the migration runs again
    monkeypatch.setattr(db, "schema_fingerprint", lambda: first + "-changed")
    db.ensure_db()
    with db.get_conn() as conn:
        assert "aux_group" in db.table_columns(conn, "meetings")

    assert core.get_meeting_meta("2026-09-16", core.MIDWEEK)["aux_group"] == ""


def test_the_same_part_is_not_given_two_meetings_running(core, people):
    """A chairman this week gets something else next week — unless nobody else
    qualifies, when filling the part beats leaving it empty."""
    from datetime import date, timedelta

    slots = core.build_midweek_slots(core.default_midweek_parts())
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    chairman = next(i for i, s in enumerate(slots) if s["role"] == "Chairman")
    last_week = (date.today() - timedelta(days=7)).isoformat()
    today = date.today().isoformat()

    core.save_schedule(last_week, core.MIDWEEK, slots,
                       {chairman: (people["Kofi Mensah"], None)}, {}, names)
    students = core.get_students()

    role_dates = core.last_role_dates("Chairman")
    assert core.held_recently(role_dates, people["Kofi Mensah"], today)
    assert not core.held_recently(role_dates, people["Nii Tetteh"], today)

    picks = core.suggest_assignments(slots, students, set(), today)
    assert picks[chairman][0] != people["Kofi Mensah"]
    assert picks[chairman][0] == people["Nii Tetteh"]      # the other chairman

    # with nobody else qualified, the part is filled rather than left empty
    core.set_suspension(people["Nii Tetteh"], True)
    students = core.get_students()
    picks = core.suggest_assignments(
        slots, students, core.get_suspended(students, today), today)
    assert picks[chairman][0] == people["Kofi Mensah"]


def test_suggest_keeps_what_is_already_chosen(core, people):
    """Suggest used to compute a pick for every slot and override whatever was
    there — five parts done by hand were silently replaced."""
    slots = core.build_midweek_slots(core.default_midweek_parts())
    today = date.today().isoformat()
    students = core.get_students()
    chairman = next(i for i, s in enumerate(slots) if s["role"] == "Chairman")
    reading = next(i for i, s in enumerate(slots) if s["role"] == "Bible Reading")

    picks = core.suggest_assignments(
        slots, students, set(), today,
        skip={chairman: (people["Nii Tetteh"], None)})
    assert picks[chairman] is None            # left alone, not overwritten
    assert picks[reading][0] is not None      # the empty one was filled

    # and the reserved person is not handed a second part
    chosen = [p for i, v in picks.items() if v for p in v if p]
    assert people["Nii Tetteh"] not in chosen


def test_hardest_slots_are_filled_first(core):
    """Taken in page order, an early slot with many candidates can take the one
    person qualified for a later one and leave that part empty."""
    # Kofi can chair or conduct; Yaw can only chair
    core.add_student("Kofi Mensah", "Brother", ["Chairman", "Bible Study Conductor"])
    core.add_student("Yaw Adjei", "Brother", ["Chairman"])
    students = core.get_students()
    ids = dict(zip(students["name"], students["id"]))
    slots = core.build_midweek_slots(core.default_midweek_parts())
    chairman = next(i for i, s in enumerate(slots) if s["role"] == "Chairman")
    cbs = next(i for i, s in enumerate(slots) if s["role"] == "Bible Study Conductor")

    picks = core.suggest_assignments(slots, students, set(), date.today().isoformat())
    assert picks[cbs][0] == ids["Kofi Mensah"]      # the only conductor
    assert picks[chairman][0] == ids["Yaw Adjei"]   # so the chair goes to Yaw


def test_ministry_parts_count_as_one_for_taking_turns(core, people):
    """Initial Presentation, Making Disciples and Explaining Your Beliefs are
    separate roles, so a same-part rule let one person take all three on
    consecutive weeks."""
    from datetime import timedelta

    slots = core.build_midweek_slots(core.default_midweek_parts())
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    ip = next(i for i, s in enumerate(slots) if s["role"] == "Initial Presentation")
    last_week = (date.today() - timedelta(days=7)).isoformat()
    core.save_schedule(last_week, core.MIDWEEK, slots,
                       {ip: (people["Ama Owusu"], None)}, {}, names)

    recent = core.last_student_part_dates()
    assert people["Ama Owusu"] in recent

    md = next(i for i, s in enumerate(slots) if s["role"] == "Making Disciples")
    picks = core.suggest_assignments(slots, core.get_students(), set(),
                                     date.today().isoformat())
    # a different ministry part the very next week goes to somebody else
    assert picks[md][0] != people["Ama Owusu"]


def test_talks_can_be_stored_and_edited(core):
    """Talk numbers and titles are kept so a weekend schedule picks one."""
    assert core.get_talks() == []
    core.save_talk("2", "Namɔ Ji Yehowa?")
    core.save_talk("10", "Yehowa Ji Wɔhewalɛ")
    core.save_talk("1", "")
    # numeric order, not alphabetical: 1, 2, 10
    assert [n for n, _ in core.get_talks()] == ["1", "2", "10"]
    assert core.talk_label("2", "Namɔ Ji Yehowa?") == "No. 2 — Namɔ Ji Yehowa?"
    assert core.talk_label("1", "") == "No. 1"

    core.save_talk("2", "A better title")          # editing replaces
    assert dict(core.get_talks())["2"] == "A better title"
    core.delete_talk("2")
    assert "2" not in dict(core.get_talks())


def test_recency_is_measured_from_the_meeting_not_today(core):
    """Working on week 2 of October, "last week" means week 1 of October
    however long afterwards you open it."""
    meeting = "2026-10-14"
    # three states in traffic-light order; the words carry the exact distance
    assert core.recency("2026-10-12", meeting) == ("🔴", "this week")
    assert core.recency("2026-10-07", meeting) == ("🔴", "last week")
    assert core.recency("2026-09-30", meeting) == ("🟡", "2 weeks ago")
    assert core.recency("2026-09-23", meeting) == ("🟡", "3 weeks ago")
    assert core.recency("2026-09-16", meeting) == ("🟢", "4 weeks ago")
    assert core.recency("2026-08-12", meeting)[0] == "🟢"
    assert core.recency(None, meeting) == core.NEVER_BAND
    # never had a part ranks with the longest wait, not against it
    assert core.NEVER_BAND[0] == "🟢"
    # the same date reads differently against a later meeting
    assert core.recency("2026-10-07", "2026-11-11")[0] == "🟢"


def test_setup_checklist_clears_as_things_are_done(core, people):
    import dashboard

    students = core.get_students()
    gaps = [what for what, _ in dashboard.setup_gaps(students)]
    assert any("congregation name" in g for g in gaps)
    assert any("S-89" in g for g in gaps)
    assert any("workbook" in g for g in gaps)

    core.set_setting("congregation", "Teshie Asafo")
    gaps = [what for what, _ in dashboard.setup_gaps(students)]
    assert not any("congregation name" in g for g in gaps)
    assert any("S-89" in g for g in gaps)             # the rest remain


def test_talks_import_in_bulk(core):
    """Two hundred outlines arrive as a list, not typed a row at a time."""
    rows = [(str(n), f"Title {n}") for n in range(1, 195)]
    total, added = core.import_talks(rows)
    assert (total, added) == (194, 194)
    assert len(core.get_talks()) == 194
    assert [n for n, _ in core.get_talks()][:3] == ["1", "2", "3"]

    # re-importing the same numbers corrects titles in place
    total, added = core.import_talks([("52", "A better title")])
    assert (total, added) == (1, 0)
    assert dict(core.get_talks())["52"] == "A better title"
    assert len(core.get_talks()) == 194

    # blank and duplicate numbers are dropped rather than stored
    total, _ = core.import_talks([("", "no number"), ("7", "x"), ("7", "again")])
    assert total == 1
    assert dict(core.get_talks())["7"] == "x"

    # replacing swaps the whole list
    total, _ = core.import_talks([("1", "Only one")], replace=True)
    assert total == 1 and len(core.get_talks()) == 1
