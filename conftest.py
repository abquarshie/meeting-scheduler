# -*- coding: utf-8 -*-
"""Shared fixtures: a fresh database per test, sample workbooks and a fake Google Sheet."""
import os
import sys
import uuid
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

APP = str(ROOT / "app.py")


DSN = os.environ.get("MEETING_DSN")


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    """Every test gets its own empty Postgres schema and no sync state."""
    if not DSN:
        pytest.skip("set MEETING_DSN to a Postgres database to run the tests")
    name = "test_" + uuid.uuid4().hex[:12]
    monkeypatch.setenv("MEETING_SCHEMA", name)
    import db
    db._pool.clear()                      # the pool is bound to the schema
    db._schema_ready.clear()
    db._all_settings.clear()
    db._role_dates.clear()
    db._student_part_dates.clear()
    db._talks.clear()
    import workbook
    workbook._workbook.clear()
    with psycopg.connect(DSN, autocommit=True) as raw:
        raw.execute(f"CREATE SCHEMA {name}")
    yield name
    db._pool.clear()
    with psycopg.connect(DSN, autocommit=True) as raw:
        raw.execute(f"DROP SCHEMA {name} CASCADE")


@pytest.fixture
def core():
    import core as c
    c.init_db()
    return c


@pytest.fixture
def people(core):
    """A small congregation. Returns {name: id}."""
    add = core.add_student
    add("Kofi Mensah", "Brother", ["Chairman", "Prayer", "Treasures Talk", "Spiritual Gems",
                                   "Living Part", "Bible Study Conductor", "Reader",
                                   "Aux Classroom Counselor"], family="Mensah family")
    add("Esi Mensah", "Sister", ["Initial Presentation", "Making Disciples"],
        family="Mensah family")
    add("Kojo Mensah", "Brother", ["Initial Presentation", "Bible Reading"],
        family="Mensah family", groups=["Child"])
    add("Ama Owusu", "Sister", ["Initial Presentation", "Making Disciples",
                                "Explaining Beliefs"])
    add("Efua Osei", "Sister", ["Initial Presentation", "Making Disciples"])
    add("Yaw Adjei", "Brother", ["Weekend Chairman", "Prayer", "Watchtower Reader"])
    add("Nii Tetteh", "Brother", ["Public Talk", "Watchtower Conductor", "Bible Reading",
                                  "Chairman"])
    df = core.get_students()
    return dict(zip(df["name"], df["id"]))


# ----------------------------------------------------------------- workbooks
def _pdf(path, pages, font=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=A4)
    if font:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont("TestFont", font))
    for lines in pages:
        if font:
            c.setFont("TestFont", 10)
        y = 800
        for line in lines:
            c.drawString(40, y, line)
            y -= 16
        c.showPage()
    c.save()
    return path.read_bytes()


def week_lines(head, book, ministry, tag, headings=True, song="Song"):
    lines = [head, book, f"{song} 76 and Prayer | Opening Comments (1 min.)"]
    if headings:
        lines.append("TREASURES FROM GOD’S WORD")
    lines += [f"1. {tag} Treasures Talk", "(10 min.)", "2. Spiritual Gems", "(10 min.)",
              "3. Bible Reading", "(4 min.) reading"]
    if headings:
        lines.append("APPLY YOURSELF TO THE FIELD MINISTRY")
    n = 4
    for k in range(ministry):
        lines += [f"{n}. Starting a Conversation", f"({2 + k % 2} min.) HOUSE TO HOUSE."]
        n += 1
    if headings:
        lines.append("LIVING AS CHRISTIANS")
    lines += [f"{n}. Keep Your Marriage Strong by", "Showing Loyalty to Each Other",
              "(15 min.) Discussion."]
    n += 1
    lines += [f"{n}. Local Needs", "(5 min.)"]
    n += 1
    lines += [f"{n}. Congregation Bible Study", "(30 min.) lfb lesson 5",
              f"Concluding Comments (3 min.) | {song} 100 and Prayer"]
    return lines


@pytest.fixture
def english_workbook(tmp_path):
    return _pdf(tmp_path / "en.pdf", [
        week_lines("SEPTEMBER 14-20", "ISAIAH 60-62", 4, "B"),
        week_lines("SEPTEMBER 21-27", "ISAIAH 63-64", 3, "C"),
    ])


@pytest.fixture
def ga_workbook(tmp_path):
    font = str(ROOT / "DejaVuSans.ttf")  # the app's own font has ɛ ɔ ŋ
    first = week_lines("SƐPTƐMBA 14-20", "YESAIA 60-62", 4, "B", False, "Lala")
    return _pdf(tmp_path / "ga.pdf", [
        week_lines("SƐPTƐMBA 7-13", "YESAIA 58-59", 2, "A", False, "Lala"),
        first[:12], first[12:],  # one week split over two pages
        week_lines("OKTOBA 5-11", "YESAIA 5-6", 3, "D", False, "Lala"),  # a week skipped
    ], font=font if Path(font).exists() else None)


@pytest.fixture
def s140_template(tmp_path):
    import docx
    d = docx.Document()
    tbl = d.add_table(rows=0, cols=5)

    def row(texts):
        r = tbl.add_row()
        for cell, text in zip(r.cells, texts):
            cell.text = text

    for _ in range(5):
        row(["[ASAFO LƐ GBƐ́I]", "", "", "", ""])
        row(["", "", "", "", ""])
        row(["[DEETI]", "", "[Gbɛ́i]", "", ""])
        for i in range(23):
            row(["0:00", f"[Saneyitso]{i}", "[Gbɛ́i]", "[Gbɛ́i]", "[Gbɛ́i]"])
    path = tmp_path / "S-140.docx"
    d.save(path)
    return path.read_bytes()


def run(at):
    at.run(timeout=90)
    assert not at.exception, at.exception
    return at


def button(at, label):
    return next(b for b in at.button if b.label == label)
