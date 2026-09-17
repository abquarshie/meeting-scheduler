# -*- coding: utf-8 -*-
"""Keep a copy of every table in a Google Sheet.

SQLite stays the working database. After any change the tables are copied to
the sheet (one worksheet per table), and when the app starts with an empty
database (e.g. after Streamlit Cloud restarts) everything is loaded back.

Secrets (Streamlit Cloud → Settings → Secrets, or .streamlit/secrets.toml):

    [gsheets]
    spreadsheet = "https://docs.google.com/spreadsheets/d/…"

    [gcp_service_account]
    type = "service_account"
    project_id = "…"
    private_key = "-----BEGIN PRIVATE KEY-----\\n…"
    client_email = "…@….iam.gserviceaccount.com"
    …the rest of the JSON key file…
"""
import hashlib

from backup import *  # noqa: F401,F403

MAX_CELL = 45000  # Google's limit is 50,000 characters per cell
_pushed = {}      # table -> hash of what was last sent (per process)
_checked = set()  # database files already checked for a restore


def config():
    """(spreadsheet ref, service-account json) or None when not set up."""
    try:
        secrets = st.secrets
        gs = secrets.get("gsheets")
        sa = secrets.get("gcp_service_account")
    except Exception:
        return None
    if not gs or not sa or not gs.get("spreadsheet"):
        return None
    return gs["spreadsheet"], json.dumps(dict(sa), sort_keys=True)


def enabled():
    return config() is not None


@st.cache_resource(show_spinner=False)
def _open(ref, sa_json):
    import gspread
    client = gspread.service_account_from_dict(json.loads(sa_json))
    return client.open_by_url(ref) if ref.startswith("http") else client.open_by_key(ref)


def _spreadsheet():
    cfg = config()
    if cfg is None:
        raise RuntimeError("Google Sheets isn't set up in the app's secrets.")
    return _open(*cfg)


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return int(value)
    return value


def _table_values(data, table):
    with get_conn() as conn:
        cols = table_columns(conn, table)
    rows = []
    for r in data.get(table, []):
        if table == "workbook_weeks" and len(r.get("data") or "") > MAX_CELL:
            week = json.loads(r["data"])
            week["text"] = ""  # the workbook text is only for cross-checking
            r = {**r, "data": json.dumps(week, ensure_ascii=False)}
        rows.append([_cell(r.get(c)) for c in cols])
    return [cols] + rows


def push(force=False):
    """Copy changed tables to the sheet. Returns the tables that were sent."""
    sheet = _spreadsheet()
    data = export_all()
    existing = {ws.title: ws for ws in sheet.worksheets()}
    sent = []
    for table in TABLES:
        values = _table_values(data, table)
        digest = hashlib.sha1(json.dumps(values, default=str).encode()).hexdigest()
        if not force and _pushed.get(table) == digest:
            continue
        ws = existing.get(table)
        if ws is None:
            ws = sheet.add_worksheet(title=table, rows=len(values), cols=len(values[0]))
        ws.resize(rows=max(len(values), 1), cols=max(len(values[0]), 1))
        ws.update(range_name="A1", values=values, value_input_option="RAW")
        _pushed[table] = digest
        sent.append(table)
    return sent


def pull():
    """Every table from the sheet, as a backup dict."""
    import gspread
    sheet = _spreadsheet()
    data = {"_version": BACKUP_VERSION}
    for table in TABLES:
        try:
            values = sheet.worksheet(table).get_all_values()
        except gspread.WorksheetNotFound:
            continue
        if not values:
            data[table] = []
            continue
        header, *rows = values
        data[table] = [dict(zip(header, row)) for row in rows]
    return data


def remember_current_state():
    """Treat what's in the database now as already copied."""
    data = export_all()
    for table in TABLES:
        values = _table_values(data, table)
        _pushed[table] = hashlib.sha1(json.dumps(values, default=str).encode()).hexdigest()


def restore_if_fresh():
    """On a fresh start, load the data back from the sheet. Returns a message."""
    path = str(db_path())
    if path in _checked or not enabled():
        return None
    _checked.add(path)
    init_db()
    if not is_empty():
        return None
    try:
        data = pull()
    except Exception as exc:  # network or permission problem
        return f"Couldn't load data from Google Sheets: {exc}"
    if not (data.get("students") or data.get("schedules")):
        return None
    import_all(data, log=False)
    log_change("Restored from Google Sheets", "app started with an empty database")
    remember_current_state()
    return "restored"


def sync_if_dirty():
    """Called at the end of every run: copy changes, never crash the page."""
    try:
        dirty = st.session_state.pop("_db_dirty", False)
    except Exception:
        return
    if not dirty or not enabled():
        return
    try:
        push()
        st.session_state["_sync_status"] = ("ok", datetime.now().strftime("%H:%M"))
    except Exception as exc:
        st.session_state["_db_dirty"] = True  # try again next time
        st.session_state["_sync_status"] = ("error", str(exc)[:200])


def status_text():
    if not enabled():
        return "warning", ("Google Sheets isn't set up, so data is lost when the app "
                           "restarts. Download a backup regularly (Admin page).")
    state = st.session_state.get("_sync_status")
    if not state:
        return "info", "☁️ Google Sheets connected."
    if state[0] == "ok":
        return "success", f"☁️ Saved to Google Sheets at {state[1]}."
    return "error", f"☁️ Google Sheets sync failed: {state[1]}"
