# Meeting Scheduler

A Streamlit app for assigning meeting parts, printing S-89 slips and exporting
the S-140 midweek schedule. It supports an auxiliary classroom, English and Ga
slips, families, suspensions and away dates, and stores everything in Postgres.

## Monthly workflow

1. **Workbook PDF.** Weeks are found from the part numbering, so English
   and Ga workbooks both work. Check the first week's date under **Week dates**
   and look over the **Weeks found** table for missing part numbers.
2. **Month overview.** See every meeting in the month and its open slots.
   Workbook weeks without a schedule can be created one at a time, or all at
   once with **Create all weeks**, which fills each from the rotation.
3. **Create or edit.** The workbook week is picked from the date, and a
   **Cross-check** panel shows the workbook text. Dropdowns list only eligible
   people, longest-waiting first for that part. **✨ Suggest** fills empty slots.
   A weekend meeting can be marked **Symposium** when one talk is shared by
   two of the congregation's brothers (guest speakers don't give them).
4. **Slips and printing.** Pick the slip language in the sidebar (English or
   Ga; it is remembered for next time), then choose one meeting or a whole
   month. Three tabs:
   **Slips & sheets** (S-89 slips on the official blank, uploaded once under
   **Admin**, the midweek schedule sheets, and the weekend schedule: the
   months picked under **Months on the weekend schedule**, two months to a
   landscape sheet at full size), **S-140 & CSV**
   (the S-140 for a month, filled from the blank stored under **Admin**, and a
   CSV of every schedule), and **Messages**: **Weekly reminders** (pick a
   week, and everyone with a part that week gets a ready-to-send WhatsApp
   message listing theirs, plus the whole week in one message) and the same
   for a whole month.
5. **Public talks.** Everything the talk coordinator needs: invitation
   letters for guest speakers, our approved outgoing speakers
   and their letter, the annual talk checklist, the talk list, and the
   details printed on the letters.
6. **Reports.** Parts and assisting per person over 3, 6 or 12 months, to spot
   anyone left out or overused.

## Participants

Each person has a category (Brother/Sister), an optional group (Child, Youth,
New student), an optional family and privileges. An assistant must be the same
category as the student or from the same family. People can be marked
inactive, given away periods, or suspended (open-ended or until a date).

## Admin page

- **Data & backup:** upload the fillable blank S-89 and the blank S-140
  (.docx) once per language, so slips and the export use the real forms; also
  a full backup file you can download and restore.
- **Settings:** congregation name, the auxiliary classroom
  default, which weekday each meeting falls on, the rotation rest period and
  assembly/convention weeks.
- **Change log:** who changed what and when.

## One-time setup

### 1. Password

In Streamlit Cloud open your app → **Settings → Secrets** and add:

```toml
[auth]
password = "choose-a-shared-password"
```

Everyone then signs in with their name and that password, and the change log
records their name. Every signed-in user has full access to everything —
participants, the workbook, month view, reports, Admin, and both meetings.
Without an `[auth]` section the app stays open to anyone with the link.

To give each person their own account instead (see `secrets.toml.example`),
still with full access for everyone — only the name in the change log
differs:

```toml
[auth.users.Kofi]
password = "first-password"

[auth.users.Ama]
password = "second-password"
```

### 2. Database

The app stores its data in Postgres. Any provider works; Neon's free tier suits
a congregation app because it wakes on the first connection instead of needing a
manual restore after a quiet spell.

1. Create a project and copy its connection string.
2. Add it to the app's Secrets:

```toml
[database]
url = "postgresql://user:password@host/dbname?sslmode=require"
```

Tables are created on first run. Nothing else is needed — the app no longer
depends on anything surviving on the server's disk.

## Project layout

Every file sits next to `app.py` (no folders), so uploading through the GitHub
website can't break the structure.

```
app.py                  entry point: sign-in, sidebar, page routing
s140.py                 S-140 template filler
constants.py            roles, privileges, slip wording
utils.py                text, date and part-slot helpers
db.py                   Postgres storage, undo snapshots and the change log
parts.py                default part lists
workbook.py             workbook PDF reader and week dates
sheets_pdf.py           printable schedule sheets and S-140 data
slips.py                S-89 slips, filled on the official blank
picking.py              eligibility, rotation, Suggest
backup.py               full backup / restore
auth.py                 sign-in (everyone has full access)
ui.py                   look and feel: sidebar, headers, section colours
core.py                 every module in one import, for tests and a Python shell
dashboard.py, participants.py, schedule.py, view.py, talks.py, month.py,
workbook_page.py, reports.py, admin.py      one file per page
conftest.py, test_*.py  automated tests (pytest)
DejaVuSans*.ttf         fonts for ɛ ɔ ŋ
config.toml             light and dark theme (copied into .streamlit/ automatically)
secrets.toml.example    template for the app's Secrets
```

## Run locally

```
pip install -r requirements-dev.txt
mkdir -p .streamlit && cp secrets.toml.example .streamlit/secrets.toml   # then edit it
streamlit run app.py
```

`secrets.toml` is git-ignored, so passwords and keys never reach GitHub.

## Tests

```
MEETING_DSN="postgresql://…" pytest -q
```

Each test gets its own throwaway Postgres schema, so
they never touch real data. Point `MEETING_DSN` at a scratch database, not the
congregation's.
