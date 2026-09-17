# -*- coding: utf-8 -*-
"""Shared fixtures: a fresh database per test, sample workbooks and a fake Google Sheet."""
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

APP = str(ROOT / "app.py")


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Every test gets its own empty database and no sync state."""
    db = tmp_path / "test.db"
    monkeypatch.setenv("MEETING_DB", str(db))
    import sheets
    sheets._checked.clear()
    sheets._pushed.clear()
    yield db


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


def legacy_db(path):
    """A database as the very first version of the app left it."""
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE students (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "name TEXT NOT NULL, gender TEXT, privileges TEXT)")
    con.execute("CREATE TABLE schedules (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "meeting_date TEXT, meeting_type TEXT, part_name TEXT, assigned_person TEXT)")
    con.executemany("INSERT INTO students (name, gender, privileges) VALUES (?, ?, ?)", [
        ("Kofi Mensah", "Brother", "Chairman, Prayer, Talk"),
        ("Ama Owusu", "Sister", "Initial Presentation"),
    ])
    con.executemany("INSERT INTO schedules (meeting_date, meeting_type, part_name, "
                    "assigned_person) VALUES (?, ?, ?, ?)", [
        ("2026-08-05", "Midweek Meeting", "Chairman", "Kofi Mensah"),
        ("2026-08-05", "Midweek Meeting", "Initial Presentation", "Ama Owusu"),
        ("2026-08-09", "Weekend Meeting", "Chairman", "Kofi Mensah"),
    ])
    con.commit()
    con.close()


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


# ------------------------------------------------------------- fake Google
class FakeWorksheet:
    def __init__(self, title):
        self.title = title
        self.values = []
        self.calls = 0

    def resize(self, rows, cols):
        self.calls += 1

    def update(self, range_name=None, values=None, value_input_option=None):
        self.calls += 1
        # Google hands everything back as text
        self.values = [["" if v is None else str(v) for v in row] for row in values]

    def get_all_values(self):
        return [list(r) for r in self.values]


class FakeSpreadsheet:
    def __init__(self):
        self.sheets = {}

    def worksheets(self):
        return list(self.sheets.values())

    def add_worksheet(self, title, rows, cols):
        self.sheets[title] = FakeWorksheet(title)
        return self.sheets[title]

    def worksheet(self, title):
        import gspread
        if title not in self.sheets:
            raise gspread.WorksheetNotFound(title)
        return self.sheets[title]


@pytest.fixture
def fake_sheet(monkeypatch):
    import sheets
    fake = FakeSpreadsheet()
    monkeypatch.setattr(sheets, "_open", lambda ref, sa: fake)
    monkeypatch.setattr(sheets, "config", lambda: ("fake-sheet", "{}"))
    return fake


def run(at):
    at.run(timeout=90)
    assert not at.exception, at.exception
    return at


def button(at, label):
    return next(b for b in at.button if b.label == label)
