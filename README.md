# Meeting Scheduler

A Streamlit app for assigning meeting parts, printing S-89 slips and exporting
the S-140 midweek schedule. It supports an auxiliary classroom, English and Ga
slips, families, suspensions and away dates, and stores everything in Postgres.

## Monthly workflow

1. **Upload Workbook PDF.** Weeks are found from the part numbering, so English
   and Ga workbooks both work. Check the first week's date under **Week dates**
   and look over the **Weeks found** table for missing part numbers.
2. **Month Overview.** See every meeting in the month and its open slots.
   Workbook weeks without a schedule can be created one at a time, or all at
   once with **Create all weeks**, which fills each from the rotation.
3. **Create Schedule.** The workbook week is picked from the date, and a
   **Cross-check** panel shows the workbook text. Dropdowns list only eligible
   people, longest-waiting first for that part. **✨ Suggest** fills empty slots.
4. **Slips and printing.** Choose one meeting or a whole month, then download
   the S-89 slips and the midweek and weekend schedule sheets. The slips print
   on the official blank S-89, which is uploaded once under **Admin**.
5. **Slips and printing** also holds the CSV of every schedule and the
   S-140 for a month, filled from the blank stored under **Admin**.
6. **Reports.** Parts and assisting per person over 3, 6 or 12 months, to spot
   anyone left out or overused.

## Participants

Each person has a category (Brother/Sister), an optional group (Child, Youth,
New student), an optional family and privileges. An assistant must be the same
category as the student or from the same family. People can be marked
inactive, given away periods, or suspended (open-ended or until a date).

## Admin page

- **Data & backup:** a full backup file you can download and restore, and the
  blank S-89 and S-140 forms the app prints on.
- **Settings:** congregation name, printing language, the auxiliary classroom
  default, and which weekday each meeting falls on.
- **Official S-89 blank:** upload the fillable blank once per language; slips
  are printed on it.
- **Interface wording:** type Ga wording for the buttons and headings, then
  choose **Ga** under ⚙️ Settings in the sidebar.
- **Change log:** who changed what and when.

## One-time setup

### 1. Password

In Streamlit Cloud open your app → **Settings → Secrets** and add:

```toml
[auth]
password = "choose-a-shared-password"
```

Everyone then signs in with their name and that password, and the change log
records their name. To give each person their own password, use `[auth.users]`
instead (see `secrets.toml.example`). Without an `[auth]` section the
app stays open to anyone with the link.

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
auth.py                 password sign-in
i18n.py                 interface wording
ui.py                   look and feel: sidebar, headers, section colours
core.py                 one import for the pages
dashboard.py, participants.py, schedule.py, view.py, month.py,
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

Each test gets its own throwaway Postgres schema and a fake Google Sheet, so
they never touch real data. Point `MEETING_DSN` at a scratch database, not the
congregation's.
