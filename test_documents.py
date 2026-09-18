# -*- coding: utf-8 -*-
"""Slips, printable schedules and the S-140."""
import io

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
