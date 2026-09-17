# Meeting Scheduler

A Streamlit app for assigning meeting parts, printing S-89 slips and exporting
the S-140 midweek schedule. It supports an auxiliary classroom, English and Ga
slips, families, suspensions and away dates, and keeps a copy of all data in
Google Sheets.

## Monthly workflow

1. **Upload Workbook PDF.** Weeks are found from the part numbering, so English
   and Ga workbooks both work. Check the first week's date under **Week dates**
   and look over the **Weeks found** table for missing part numbers.
2. **Month Overview.** See every meeting in the month and its open slots.
   Workbook weeks without a schedule have a **Create** button.
3. **Create Schedule.** The workbook week is picked from the date, and a
   **Cross-check** panel shows the workbook text. Dropdowns list only eligible
   people, longest-waiting first for that part. **✨ Suggest** fills empty slots.
4. **View Schedules / Month Overview.** Download S-89 slips (one meeting or the
   whole month), copy WhatsApp reminders (one at a time or all at once) and
   print the schedule.
5. **Export.** CSV, or upload the blank S-140 template to get `Month Year.docx`.
6. **Reports.** Parts and assisting per person over 3, 6 or 12 months, to spot
   anyone left out or overused.

## Participants

Each person has a category (Brother/Sister), an optional group (Child, Youth,
New student), an optional family and privileges. An assistant must be the same
category as the student or from the same family. People can be marked
inactive, given away periods, or suspended (open-ended or until a date).

## Admin page

- **Data & backup:** Google Sheets status, copy/load buttons, and a full backup
  file you can download and restore.
- **Meeting days:** which weekday your midweek and weekend meetings fall on.
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

### 2. Google Sheets

1. Go to <https://console.cloud.google.com>, create a project, and enable the
   **Google Sheets API** and **Google Drive API**.
2. **IAM & Admin → Service Accounts → Create service account.** Open it,
   go to **Keys → Add key → JSON**, and download the file.
3. Create an empty Google Sheet. **Share** it with the service account's
   `client_email` (from the JSON file) as **Editor**.
4. In the app's Secrets, add the sheet link and the JSON fields (the full
   template is in `secrets.toml.example`):

```toml
[gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/…/edit"

[gcp_service_account]
type = "service_account"
project_id = "…"
private_key = "-----BEGIN PRIVATE KEY-----\n…\n-----END PRIVATE KEY-----\n"
client_email = "…@….iam.gserviceaccount.com"
# …and the other fields from the JSON file
```

5. Open **Admin → Data & backup** and click **Copy everything to Google Sheets
   now**. The sheet gets one tab per table.

From then on every change is copied automatically, and when Streamlit Cloud
restarts with an empty database the app loads everything back from the sheet.
Don't edit the sheet by hand; treat it as the app's storage.

## Project layout

Every file sits next to `app.py` (no folders), so uploading through the GitHub
website can't break the structure.

```
app.py                  entry point: sign-in, sidebar, page routing
s140.py                 S-140 template filler
constants.py            roles, privileges, slip wording
utils.py                text, date and part-slot helpers
db.py                   SQLite storage and the change log
parts.py                default part lists
workbook.py             workbook PDF reader and week dates
pdfs.py                 slips, schedule PDF, S-140 data, reminders
picking.py              eligibility, rotation, Suggest
backup.py               full backup / restore
sheets.py               Google Sheets copy and restore
auth.py                 password sign-in
i18n.py                 interface wording
core.py                 one import for the pages
dashboard.py, participants.py, schedule.py, view.py, month.py,
workbook_page.py, reports.py, export.py, admin.py      one file per page
conftest.py, test_*.py  automated tests (pytest)
DejaVuSans*.ttf         fonts for ɛ ɔ ŋ
config.toml             dark theme (copied into .streamlit/ automatically)
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
pytest -q
```

The tests use their own temporary database and a fake Google Sheet, so they
never touch real data.
