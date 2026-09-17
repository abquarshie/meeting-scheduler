# -*- coding: utf-8 -*-
"""Reading workbook PDFs into weeks, parts and dates."""
from datetime import date


def test_english_weeks_parts_and_wrapped_titles(core, english_workbook):
    weeks, empty, _ = core.parse_brochure(english_workbook)
    assert list(weeks) == ["SEPTEMBER 14–20", "SEPTEMBER 21–27"]
    assert not empty
    first = weeks["SEPTEMBER 14–20"]
    assert [p["part_no"] for p in first["parts"]] == list(range(1, 11))
    assert first["gaps"] == []
    titles = {p["part_no"]: p["title"] for p in first["parts"]}
    assert titles[8] == "Keep Your Marriage Strong by Showing Loyalty to Each Other"
    roles = {p["part_no"]: p["role"] for p in first["parts"]}
    assert roles[3] == "Bible Reading" and roles[10] == "Bible Study Conductor"
    assert {p["section"] for p in first["parts"] if 4 <= p["part_no"] <= 7} == {"Ministry"}
    assert first["songs"] == ["76", "100"]


def test_ga_weeks_split_pages_and_skipped_week(core, ga_workbook):
    weeks, _, _ = core.parse_brochure(ga_workbook)
    labels = list(weeks)
    assert labels == ["SƐPTƐMBA 7–13", "SƐPTƐMBA 14–20", "OKTOBA 5–11"]
    assert len(weeks["SƐPTƐMBA 14–20"]["parts"]) == 10  # continued on the next page
    # without English headings the sections are still guessed sensibly
    parts = weeks["SƐPTƐMBA 14–20"]["parts"]
    assert parts[0]["section"] == "Treasures"
    assert parts[3]["section"] == "Ministry"
    assert parts[-1]["role"] == "Bible Study Conductor"

    first, sure = core.guess_first_monday(weeks, "mwb_GA_202609.pdf")
    assert (first, sure) == (date(2026, 9, 7), True)
    core.assign_dates(weeks, first)
    assert core.week_for_date(weeks, "2026-09-10") == "SƐPTƐMBA 7–13"
    assert core.week_for_date(weeks, "2026-09-17") == "SƐPTƐMBA 14–20"
    assert core.week_for_date(weeks, "2026-10-01") is None  # the skipped week
    assert core.week_for_date(weeks, "2026-10-08") == "OKTOBA 5–11"


def test_guess_without_month_names_is_flagged(core, ga_workbook):
    weeks, _, _ = core.parse_brochure(ga_workbook)
    first, sure = core.guess_first_monday(weeks, "workbook.pdf")
    assert first.weekday() == 0 and first.day == 7 and not sure


def test_gaps_are_reported(core):
    text = "\n".join(["1. Talk (10 min.)", "2. Gems (10 min.)", "3. Bible Reading (4 min.)",
                      "4. Starting a Conversation (3 min.)", "7. Living Part (15 min.)",
                      "8. Another Part", "9. Congregation Bible Study (30 min.)"])
    from scheduler.workbook import _parse_week
    parts, _, gaps = _parse_week(text)
    assert gaps == [5, 6]
    assert [p["part_no"] for p in parts] == [1, 2, 3, 4, 7, 8, 9]


def test_workbook_is_stored(core, english_workbook):
    weeks, _, _ = core.parse_brochure(english_workbook)
    first, _ = core.guess_first_monday(weeks, "mwb_E_202609.pdf")
    core.save_workbook(core.assign_dates(weeks, first), "mwb_E_202609.pdf")
    stored, name = core.load_workbook()
    assert name == "mwb_E_202609.pdf"
    assert stored["SEPTEMBER 21–27"]["start"] == "2026-09-21"
