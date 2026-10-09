# -*- coding: utf-8 -*-
"""The WhatsApp cards: what they say, and that they draw."""
import io
from datetime import date, timedelta

from PIL import Image

import card_image as ci


def _png_size(png):
    return Image.open(io.BytesIO(png)).size


def _week(core, people):
    """Midweek 14 Oct (classroom on) and weekend 18 Oct with a guest."""
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    mid = core.apply_aux(core.build_midweek_slots(core.default_midweek_parts()), True)
    picks = {}
    for i, s in enumerate(mid):
        if s["role"] == "Chairman":
            picks[i] = (people["Kofi Mensah"], None)
        elif s["role"] == "Initial Presentation" and s["hall"] == core.MAIN_HALL:
            picks[i] = (people["Ama Owusu"], people["Efua Osei"])
        elif s["role"] == "Bible Reading" and s["hall"] != core.MAIN_HALL:
            picks[i] = (people["Kojo Mensah"], None)
        elif s["role"] == "Bible Study Conductor":
            picks[i] = (people["Kofi Mensah"], None)
        elif s["role"] == "Reader":
            picks[i] = (people["Nii Tetteh"], None)
    core.save_schedule("2026-10-14", core.MIDWEEK, mid, picks,
                       {"book": "YEREMIA 34-36", "opening_song": "Lala 76",
                        "aux": True}, names)
    wk = core.default_weekend_slots()
    talk = next(i for i, s in enumerate(wk) if s["role"] == "Public Talk")
    core.save_schedule("2026-10-18", core.WEEKEND, wk,
                       {0: (people["Yaw Adjei"], None), talk: (None, None),
                        talk + 10000: "Jonathan Adjei",
                        talk + 20000: "Dansoman Beach Ga"},
                       {"talk_number": "12", "talk_title": "Rely on Jehovah"}, names)
    return core.get_schedules()


def test_week_card_says_every_part(core, people):
    core.set_setting("congregation", "Ussher Town Ga")
    spec = ci.week_card_spec(_week(core, people), "2026-10-16")
    assert spec["congregation"] == "Ussher Town Ga"
    assert spec["subtitle"] == "Week 2 of October · 12–18 Oct 2026"
    mid, wk = spec["meetings"]
    assert mid["eyebrow"] == "WEDNESDAY · 14 OCTOBER"
    assert mid["title"] == "Midweek Meeting"
    assert mid["detail"] == "YEREMIA 34-36 · Song 76"      # the sheet's song word
    rows = {(r["part"], r["room"]): r for s in mid["sections"] for r in s["rows"]}
    assert rows[("Chairman", "")]["who"] == "Kofi Mensah"
    assert rows[("4. Initial Presentation (3 min)", "")]["who"] == \
        "Ama Owusu & Efua Osei"
    assert rows[("3. Bible Reading (4 min)", "Aux 1")]["who"] == "Kojo Mensah"
    assert rows[("5. Making Disciples (4 min)", "")]["who"] == ""   # shows —
    # the study's reader is a note under the conductor, not a row of its own
    study = rows[("8. Congregation Bible Study (30 min)", "")]
    assert study["note"] == "Reader: Nii Tetteh"
    assert not any(p == "Congregation Bible Study Reader" for p, _ in rows)
    # the closing prayer ends Living rather than a section of one row
    assert [s["key"] for s in mid["sections"]] == \
        ["Opening", "Treasures", "Ministry", "Living"]

    talk = next(r for s in wk["sections"] for r in s["rows"]
                if r["part"] == "Public Talk & Closing Prayer")
    assert talk["who"] == "Jonathan Adjei"
    assert talk["note"] == "Guest · Dansoman Beach Ga"
    assert wk["detail"] == "Public Talk No. 12 — “Rely on Jehovah”"
    assert wk["sections"][0]["title"] == ""        # no heading repeating the title
    assert spec["chip"].startswith("2 meetings · ")

    png = ci.render_card(spec)
    width, height = _png_size(png)
    assert width == 1440 and height > 2000


def test_week_card_headings_follow_the_slip_language(core, people):
    spec = ci.week_card_spec(_week(core, people), "2026-10-16", "Ga")
    mid, wk = spec["meetings"]
    assert mid["title"] == "Wɔshiɛmɔ Kɛ Wɔshihilɛ Kpee"
    assert wk["title"] == "Otsi Naagbee Kpee"
    assert [s["title"] for s in mid["sections"]][:2] == \
        ["Hiɛkpamɔ", "Nyɔŋmɔ Wiemɔ Lɛ Mli Jwetrii"]
    parts = [r["part"] for s in mid["sections"] + wk["sections"] for r in s["rows"]]
    assert "Sɛinɔtalɔ" in parts and "Maŋshiɛmɔ & Sɔlemɔ" in parts
    rooms = {r["room"] for s in mid["sections"] for r in s["rows"]} - {""}
    assert rooms == {"Asa 2"}
    talk = next(r for r in wk["sections"][0]["rows"] if r["note"])
    assert talk["note"].startswith("Wielɔ ni afɔ lɛ nine")
    assert "Lala 76" in mid["detail"]
    assert _png_size(ci.render_card(spec))[0] == 1440


def test_an_assembly_week_and_an_empty_week(core, people):
    core.mark_event_week("2026-10-14", "convention")
    spec = ci.week_card_spec(core.get_schedules(), "2026-10-14", "Ga")
    assert [m["title"] for m in spec["meetings"]] == ["Kpokpaa wulu Nɔ Kpee Otsi"]
    assert not spec["meetings"][0]["sections"]
    ci.render_card(spec)

    empty = ci.week_card_spec(core.get_schedules(), "2026-11-04")
    assert empty["meetings"] == [] and empty["empty"]
    ci.render_card(empty)


def test_person_card(core, people):
    rows = _week(core, people)
    items = core.month_assignments_for(rows, people["Efua Osei"], "2026-10")
    spec = ci.person_card_spec("Efua Osei", "Sister", "2026-10", items)
    assert spec["title"] == "Hello, Sister Efua Osei"
    assert spec["subtitle"] == "Your meeting assignments · October 2026"
    assert spec["chip"] == "1 assignment"
    (tile,) = spec["tiles"]
    assert (tile["day"], tile["month"]) == ("14", "OCT")
    assert tile["sub"] == "assisting Ama Owusu"
    assert tile["section"] == "Ministry"          # its colour on the date block

    kofi = core.month_assignments_for(rows, people["Kofi Mensah"], "2026-10")
    ga = ci.person_card_spec("Kofi Mensah", "Brother", "2026-10", kofi, "Ga")
    assert ga["title"] == "Hello, Brother Kofi Mensah"
    assert all("WƆSHIƐMƆ" in t["eyebrow"] for t in ga["tiles"])
    width, _ = _png_size(ci.render_card(ga))
    assert width == 1440


def test_long_names_and_titles_wrap_instead_of_running_off(core):
    long = "Kwa Je Lɛŋ Yaka Yiŋsusumɔi Lɛ, Dii Maŋtsɛyeli Lɛ He Nibii Ni Yɔɔ Diɛŋtsɛ"
    spec = {"kind": "week", "congregation": "A Congregation With A Very Long Name Indeed",
            "title": ci.CARD_TEXT["title"], "subtitle": "Week 1", "chip": "",
            "empty": "", "footer": ["a", "b"],
            "meetings": [{"eyebrow": "X", "title": "Midweek Meeting", "detail": long,
                          "sections": [{"key": "Ministry", "title": "Ministry",
                                        "rows": [{"part": long, "room": "Aux 1",
                                                  "who": "Naa Ayeley Quaye & "
                                                         "Theophilus Quarcoo-Mensah",
                                                  "note": ""}]}]}]}
    part, who, _, _ = ci._row_layout(spec["meetings"][0]["sections"][0]["rows"][0],
                                     ci.S(360), ci.S(260))
    assert len(part) > 1
    assert who[0].endswith("&")                   # the pair breaks at "&"
    ci.render_card(spec)


def test_messages_tab_offers_the_image(people, core):
    from streamlit.testing.v1 import AppTest
    from conftest import APP, run
    names = dict(zip(core.get_students()["id"], core.get_students()["name"]))
    monday = date.today() - timedelta(days=date.today().weekday())
    core.save_schedule((monday + timedelta(days=2)).isoformat(), core.MIDWEEK,
                       core.build_midweek_slots(core.default_midweek_parts()),
                       {0: (people["Kofi Mensah"], None)}, {}, names)
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    at.session_state["menu"] = "Slips and printing"
    run(at)
    labels = [b.label for b in at.get("download_button")]
    assert labels.count("Download image") == 2      # the week, and one person
    assert any(c.value.startswith("*Meeting assignments") for c in at.code)
