# -*- coding: utf-8 -*-
"""Slips, printable schedules and the S-140."""
import io
from pathlib import Path

import pytest

import docx
import pypdf


def _text(pdf_bytes):
    return "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages)


def test_slips_escape_names_and_tick_rooms(core):
    rows = [
        {"person": "Ama & <Kofi>", "assistant": "Ɛfua Ɔsei", "part_no": 4,
         "part_name": "x", "meeting_date": "2026-09-16", "hall": core.MAIN_HALL},
        {"person": "Nii Ŋmɛnɛ", "assistant": None, "part_no": 5,
         "part_name": "x", "meeting_date": "2026-09-16", "hall": core.AUX_HALL},
    ]
    text = _text(core.generate_slips_pdf(rows, core.TRANSLATIONS["Ga"]))
    assert "Ama & <Kofi>" in text
    assert "16 September 2026" in text
    assert text.count("[X]") == 2   # blank spare slips stay unticked


def _full_week(core, people, aux=True):
    weeks = {"W": {"parts": core.default_midweek_parts()}}
    slots = core.apply_aux(core.build_midweek_slots(weeks["W"]["parts"]), aux)
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    picks = {}
    for i, s in enumerate(slots):
        if s["role"] == "Aux Classroom Counselor":
            picks[i] = (people["Kofi Mensah"], None)
        elif s["student_part"]:
            aux_slot = s["hall"] == core.AUX_HALL
            picks[i] = (people["Efua Osei" if aux_slot else "Ama Owusu"],
                        people["Ama Owusu" if aux_slot else "Efua Osei"]
                        if s["needs_assistant"] else None)
        else:
            picks[i] = (people["Kofi Mensah"], None)
    core.save_schedule("2026-09-16", core.MIDWEEK, slots, picks,
                       {"heading": "SEPTEMBER 14–20", "aux": aux,
                        "opening_song": "Song 1"}, names)


def test_schedule_pdf_and_talk_title(core, people):
    _full_week(core, people)
    slots = core.default_weekend_slots()
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    core.save_schedule("2026-09-20", core.WEEKEND, slots,
                       {2: (people["Nii Tetteh"], None)},
                       {"talk_number": "12", "talk_title": "Is God Interested in You?"},
                       names)
    pdf = core.generate_schedule_pdf(
        [("2026-09-16", core.MIDWEEK), ("2026-09-20", core.WEEKEND)], core.get_schedules())
    text = _text(pdf)
    assert "Auxiliary classroom" in text
    assert "No. 12" in text and "Is God Interested in You?" in text


def test_schedule_pdf_in_ga(core, people):
    """Section headings switch language; the scripture reading, when saved,
    replaces the week label on the blue heading line."""
    _full_week(core, people)
    core.save_schedule("2026-09-16", core.MIDWEEK,
                       core.apply_aux(core.build_midweek_slots(
                           core.default_midweek_parts()), True),
                       {}, {"heading": "SEPTEMBER 14–20", "book": "YEREMIA 32-33",
                            "aux": True}, {})
    text_en = _text(core.generate_schedule_pdf(
        [("2026-09-16", core.MIDWEEK)], core.get_schedules()))
    assert "Treasures From God" in text_en
    assert "YEREMIA 32-33" in text_en          # the book line, not the week label
    assert "SEPTEMBER 14" not in text_en

    text_ga = _text(core.generate_schedule_pdf(
        [("2026-09-16", core.MIDWEEK)], core.get_schedules(), core.TRANSLATIONS["Ga"]))
    assert "Nyɔŋmɔ Wiemɔ" in text_ga
    assert "Treasures From God" not in text_ga
    assert "YEREMIA 32-33" in text_ga           # the reading itself is language-neutral


def test_s140_fills_both_halls(core, people, s140_template):
    _full_week(core, people)
    data, skipped = core.build_s140_data([("2026-09-16", core.MIDWEEK)],
                                         core.get_schedules(), "TEST CONG", "GROUP")
    assert not skipped and data["aux"] and data["clear_asa2"] is False
    week = data["weeks"][0]
    assert week["treasures"][2]["name2"] == "Efua Osei"
    assert week["aux_counselor"] == "Kofi Mensah"
    doc = docx.Document(io.BytesIO(core.fill_s140(s140_template, data)))
    cells = [c.text for r in doc.tables[0].rows for c in r.cells]
    assert "Efua Osei/Ama Owusu" in cells and "Ama Owusu/Efua Osei" in cells
    assert not any("0:00" == c for c in cells)


def test_a_second_auxiliary_classroom_flows_through(core):
    """The app only offers one auxiliary classroom, but nothing downstream
    should silently drop a second one if a schedule ever carries it."""
    slots = core.build_midweek_slots(core.default_midweek_parts())
    reading = next(s for s in slots if s["role"] == "Bible Reading")
    slots = slots + [
        {**reading, "hall": "aux_1"},
        {**reading, "hall": "aux_2"},
    ]
    picks = {len(slots) - 2: (None, None), len(slots) - 1: (None, None)}
    core.add_student("Adjeley Ayi", "Sister", ["Bible Reading"])
    core.add_student("Naa Koshie", "Sister", ["Bible Reading"])
    ids = dict(zip(core.get_students()["name"], core.get_students()["id"]))
    names = {v: k for k, v in ids.items()}
    picks = {len(slots) - 2: (ids["Adjeley Ayi"], None),
             len(slots) - 1: (ids["Naa Koshie"], None)}
    core.save_schedule("2026-09-16", core.MIDWEEK, slots, picks, {"aux": True}, names)

    rows = core.get_schedules()
    assert set(rows["hall"]) == {"main_hall", "aux_1", "aux_2"}

    # the slip ticks the third box, not the first
    slip_rows = core.slip_rows_for(rows)
    assert {r["hall"] for r in slip_rows} >= {"aux_1", "aux_2"}
    text = _text(core.generate_slips_pdf(slip_rows, core.TRANSLATIONS["English"]))
    assert "Auxiliary classroom 2" in text
    assert text.count("[X]") == len(slip_rows)     # every slip has a room ticked

    # the part label names the room it is in
    label = core.slot_label({**reading, "hall": "aux_2"})
    assert "Auxiliary classroom 2" in label

    # and the S-140 pairing treats it as a classroom, not a duplicate main-hall part
    data, skipped = core.build_s140_data([("2026-09-16", core.MIDWEEK)], rows,
                                         "TEST CONG", "GROUP")
    assert not skipped and data["aux"]
    titles = [i["title"] for i in data["weeks"][0]["treasures"]]
    assert titles.count("Bible Reading") == 1      # not repeated once per classroom


def test_printed_schedule_is_fully_ga(core, people):
    """Interface stays English; everything on the printed sheet is Ga."""
    _full_week(core, people)
    rows = core.get_schedules()
    text = _text(core.generate_schedule_pdf(
        [("2026-09-16", core.MIDWEEK)], rows, core.TRANSLATIONS["Ga"]))

    # section headings, meeting name and room label all in Ga
    assert "Nyɔŋmɔ Wiemɔ" in text and "Hii Shi Akɛ Kristofonyo" in text
    assert "Wɔshiŋmɔ" in text
    assert "Asa 2" in text                         # the auxiliary classroom

    for english in ("Treasures From God", "Living as Christians",
                    "Midweek Meeting", "Auxiliary classroom"):
        assert english not in text, f"{english!r} still on the Ga sheet"


def test_weekend_sheet_is_ga(core, people):
    slots = core.default_weekend_slots()
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    core.save_schedule("2026-09-20", core.WEEKEND, slots,
                       {2: (people["Nii Tetteh"], None)}, {}, names)
    text = _text(core.generate_schedule_pdf(
        [("2026-09-20", core.WEEKEND)], core.get_schedules(), core.TRANSLATIONS["Ga"]))
    assert "Otsi Naagbee Kpee" in text
    assert "Weekend Meeting" not in text


def test_interface_labels_stay_english(core):
    """slot_label without hall names is the interface version."""
    slot = core.make_slot("Bible Reading", "Bible Reading", "Treasures",
                          3, 4, core.AUX_HALL)
    assert "Auxiliary classroom 1" in core.slot_label(slot)
    ga_rooms = {h: core.TRANSLATIONS["Ga"][h] for h in core.HALLS}
    assert "Asa 2" in core.slot_label(slot, ga_rooms)


def test_visitor_may_say_the_closing_prayer(core, people):
    """A guest speaker is often asked to close. The flag must also survive
    reopening a saved schedule, or the option vanishes on the next edit."""
    slots = core.default_weekend_slots()
    by_role = {(s["role"], s["title"]): s for s in slots}
    assert by_role[("Public Talk", "Public Talk Speaker")]["allow_visitor"]
    assert by_role[("Prayer", "Closing Prayer")]["allow_visitor"]
    assert not by_role[("Prayer", "Opening Prayer")]["allow_visitor"]
    assert not by_role[("Weekend Chairman", "Chairman")]["allow_visitor"]

    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    closing = next(i for i, s in enumerate(slots)
                   if s["role"] == "Prayer" and s["title"] == "Closing Prayer")
    talk = next(i for i, s in enumerate(slots) if s["role"] == "Public Talk")
    core.save_schedule("2026-09-27", core.WEEKEND, slots,
                       {talk + 10000: "Bro. Addo — Osu",
                        closing + 10000: "Bro. Tetteh — Osu"}, {}, names)

    reopened, _, visitors = core.load_schedule("2026-09-27", core.WEEKEND,
                                               core.get_schedules())
    flags = {(s["role"], s["title"]): s["allow_visitor"] for s in reopened}
    assert flags[("Prayer", "Closing Prayer")]        # still offered on re-edit
    assert flags[("Public Talk", "Public Talk Speaker")]
    assert not flags[("Prayer", "Opening Prayer")]
    assert "Bro. Tetteh — Osu" in visitors.values()

    text = _text(core.generate_schedule_pdf([("2026-09-27", core.WEEKEND)],
                                            core.get_schedules()))
    assert "Bro. Tetteh — Osu" in text


def _weekend_with_guest(core, people):
    slots = core.default_weekend_slots()
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    talk = next(i for i, s in enumerate(slots) if s["role"] == "Public Talk")
    closing = next(i for i, s in enumerate(slots)
                   if s["role"] == "Prayer" and s["title"] == "Closing Prayer")
    picks = {i: (people["Kofi Mensah"], None) for i, s in enumerate(slots)}
    picks[talk] = (None, None)
    picks[talk + 10000] = "Bro. Addo — Osu"
    picks[closing] = (None, None)
    picks[closing + 10000] = "Bro. Tetteh — Osu"
    core.save_schedule("2026-09-27", core.WEEKEND, slots, picks,
                       {"talk_number": "12", "talk_title": "Is God Interested in You?"},
                       names)


def test_weekend_sheet_order_and_guest(core, people):
    """The closing prayer ends the sheet; a visitor is marked as a guest."""
    _weekend_with_guest(core, people)
    text = _text(core.generate_schedule_pdf([("2026-09-27", core.WEEKEND)],
                                            core.get_schedules()))
    for word in ("Chairman", "Public Talk", "Watchtower Study", "Theme",
                 "Guest speaker", "Opening Prayer", "Closing Prayer"):
        assert word in text, word
    assert text.index("Opening Prayer") < text.index("Public Talk")
    assert text.index("Public Talk") < text.index("Watchtower Study")
    assert text.index("Watchtower Study") < text.index("Closing Prayer")
    assert text.rstrip().index("Closing Prayer") > text.index("Chairman")
    assert "Bro. Tetteh — Osu" in text and "Bro. Addo — Osu" in text


def test_weekend_sheet_in_ga_has_no_english(core, people):
    _weekend_with_guest(core, people)
    text = _text(core.generate_schedule_pdf([("2026-09-27", core.WEEKEND)],
                                            core.get_schedules(),
                                            core.TRANSLATIONS["Ga"]))
    for word in ("Otsi Naagbee Kpee", "Sɛinɔtalɔ", "Maŋshiɛmɔ",
                 "Buu Mɔɔ Nikasemɔ", "Kanelɔ", "Saneyitso",
                 "Wielɔ ni afɔ lɛ nine", "Sɔlemɔ"):
        assert word in text, word
    for english in ("Chairman", "Public Talk", "Watchtower Study", "Theme",
                    "Guest speaker", "Closing Prayer", "Weekend Meeting"):
        assert english not in text, f"{english!r} leaked onto the Ga sheet"


def test_midweek_and_weekend_get_different_layouts(core, people):
    """One call, two sheets: the midweek running order and the weekend
    programme are laid out differently."""
    _full_week(core, people)
    _weekend_with_guest(core, people)
    text = _text(core.generate_schedule_pdf(
        [("2026-09-16", core.MIDWEEK), ("2026-09-27", core.WEEKEND)],
        core.get_schedules()))
    assert "Midweek Meeting" in text and "Weekend Meeting" in text
    assert "Treasures From God" in text          # midweek sections
    assert "Watchtower Study" in text            # weekend parts
    assert text.index("Midweek Meeting") < text.index("Weekend Meeting")


def test_auxiliary_classroom_group_is_printed(core, people):
    """Which group is using the classroom is stored per week and printed
    beside the counselor."""
    slots = core.apply_aux(core.build_midweek_slots(core.default_midweek_parts()), True)
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    counselor = next(i for i, s in enumerate(slots)
                     if s["role"] == "Aux Classroom Counselor")
    core.save_schedule("2026-09-16", core.MIDWEEK, slots,
                       {counselor: (people["Kofi Mensah"], None)},
                       {"aux": True, "aux_group": "1"}, names)
    assert core.get_meeting_meta("2026-09-16", core.MIDWEEK)["aux_group"] == "1"

    text = _text(core.generate_schedule_pdf([("2026-09-16", core.MIDWEEK)],
                                            core.get_schedules()))
    assert "Auxiliary classroom 1" in text and "Group 1" in text

    ga = _text(core.generate_schedule_pdf([("2026-09-16", core.MIDWEEK)],
                                          core.get_schedules(),
                                          core.TRANSLATIONS["Ga"]))
    assert "Asa 2" in ga and "Kuu 1" in ga
    assert "Group 1" not in ga

    # no group entered: the room is still named, with nothing after it
    core.save_schedule("2026-09-16", core.MIDWEEK, slots,
                       {counselor: (people["Kofi Mensah"], None)},
                       {"aux": True, "aux_group": ""}, names)
    plain = _text(core.generate_schedule_pdf([("2026-09-16", core.MIDWEEK)],
                                             core.get_schedules()))
    assert "Auxiliary classroom 1" in plain and "Group" not in plain


S89_BLANK = Path(__file__).resolve().parent / "tests_data" / "S-89_s-Mlt_GA.pdf"


@pytest.mark.skipif(not S89_BLANK.is_file(), reason="blank S-89 not in the repo")
def test_official_s89_is_filled_not_redrawn(core):
    """Printing on the real form gets its exact wording, so the app never has
    to carry a hand-typed copy of it."""
    blank = S89_BLANK.read_bytes()
    rows = [
        {"person": "Ɛfua Ɔsei", "assistant": "Naa Ŋmɛnɛ", "part_no": 4,
         "part_name": "x", "meeting_date": "2026-09-23", "hall": "aux_1"},
        {"person": "Samuel Oquaye", "assistant": None, "part_no": 5,
         "part_name": "x", "meeting_date": "2026-09-23", "hall": "aux_2"},
        {"person": "Vera Akitah", "assistant": None, "part_no": 3,
         "part_name": "x", "meeting_date": "2026-09-23", "hall": core.MAIN_HALL},
    ]
    text = _text(core.fill_s89(blank, rows))

    # the form's own wording, which the app does not store anywhere. Its Ga
    # labels cannot be read back by pypdf (the form's fonts carry no Unicode
    # mapping, as the workbook's do not), so check what does extract.
    assert "KPEE ASAIM" in text                  # the form's title
    assert "Asa 1" in text and "Asa 3" in text   # its room list
    # our values, Ga characters intact
    assert "Ɛfua Ɔsei" in text and "Naa Ŋmɛnɛ" in text
    assert "23 September 2026" in text
    assert text.count("X") == 3                  # one room ticked per filled slip

    # four slips to a page: three rows plus a blank still fills one sheet
    import pypdf, io
    assert len(pypdf.PdfReader(io.BytesIO(core.fill_s89(blank, rows))).pages) == 1
    assert len(pypdf.PdfReader(io.BytesIO(core.fill_s89(blank, rows * 2))).pages) == 2


@pytest.mark.skipif(not S89_BLANK.is_file(), reason="blank S-89 not in the repo")
def test_slip_printing_falls_back_without_a_blank(core):
    """No blank stored, or a PDF that isn't the S-89: print our own slip rather
    than failing the download."""
    rows = [{"person": "Kofi Mensah", "assistant": None, "part_no": 3,
             "part_name": "x", "meeting_date": "2026-09-23", "hall": core.MAIN_HALL}]
    own = _text(core.slips_pdf(rows, core.TRANSLATIONS["Ga"], "Ga"))
    assert "Kofi Mensah" in own

    assert "KRISTOWALA" in own                   # our own slip's heading

    core.save_template("s89_Ga", "S-89.pdf", S89_BLANK.read_bytes())
    official = _text(core.slips_pdf(rows, core.TRANSLATIONS["Ga"], "Ga"))
    assert "KPEE ASAIM" in official              # now the real form
    assert "KRISTOWALA" not in official
    assert "Kofi Mensah" in official

    with pytest.raises(core.S89Error):
        core.fill_s89(b"%PDF-1.4\n%%EOF\n", rows)
