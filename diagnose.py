# -*- coding: utf-8 -*-
"""Temporary diagnostic page.

Deploy this INSTEAD of app.py (Streamlit Cloud → Settings → Main file path →
diagnose.py) when the app shows "Oh no. Error running app." It reports what is
actually wrong on the page, so you don't have to find the log panel.

Delete it once the app runs.
"""
import importlib
import sys
import traceback
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Diagnose", layout="wide")
st.title("Meeting Scheduler — startup check")
st.caption(f"Python {sys.version.split()[0]}")

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- 1. packages
st.header("1. Packages")
rows = []
for name, why in [
    ("streamlit", "the app framework"),
    ("pandas", "tables"),
    ("psycopg", "Postgres driver — NEW, must be in requirements.txt"),
    ("psycopg_pool", "connection pool — NEW, must be in requirements.txt"),
    ("pypdf", "reads the workbook PDF"),
    ("reportlab", "makes the slips"),
    ("docx", "fills the S-140"),
    ("gspread", "Google Sheets export"),
]:
    try:
        mod = importlib.import_module(name)
        rows.append({"package": name, "status": "ok",
                     "version": getattr(mod, "__version__", ""), "used for": why})
    except Exception as exc:
        rows.append({"package": name, "status": f"MISSING — {exc}",
                     "version": "", "used for": why})
st.dataframe(rows, width="stretch", hide_index=True)
if any(r["status"] != "ok" for r in rows):
    st.error("A package above is missing. Check requirements.txt in the repo, "
             "then reboot the app from Manage app.")

# ---------------------------------------------------------------- 2. app files
st.header("2. App files")
expected = [
    "app.py", "core.py", "constants.py", "utils.py", "db.py", "parts.py",
    "workbook.py", "pdfs.py", "picking.py", "backup.py", "sheets.py", "auth.py",
    "i18n.py", "ui.py", "s140.py", "admin.py", "dashboard.py", "export.py",
    "month.py", "participants.py", "reports.py", "schedule.py", "view.py",
    "workbook_page.py", "requirements.txt",
]
missing = [f for f in expected if not (HERE / f).is_file()]
if missing:
    st.error("Missing from the repository: " + ", ".join(missing))
else:
    st.success(f"All {len(expected)} files present.")

# --- are they the NEW versions? the Postgres port removed/added these names ---
checks = [
    ("db.py", "def dsn(", True, "db.py is the new Postgres version"),
    ("db.py", "import sqlite3", False,
     "db.py still imports sqlite3 — it is the OLD file"),
    ("app.py", "restore_if_fresh", False,
     "app.py still calls restore_if_fresh() — it is the OLD file and will crash"),
    ("constants.py", "def db_path", False,
     "constants.py still defines db_path() — it is the OLD file"),
    ("sheets.py", "def restore_if_fresh", False,
     "sheets.py still defines restore_if_fresh() — it is the OLD file"),
    ("requirements.txt", "psycopg", True, "requirements.txt lists psycopg"),
]
problems = []
for fname, needle, want_present, message in checks:
    path = HERE / fname
    if not path.is_file():
        continue
    present = needle in path.read_text(encoding="utf-8", errors="replace")
    if present != want_present:
        problems.append(message)
if problems:
    st.error("Mixed old and new files:\n\n" + "\n\n".join(f"- {p}" for p in problems))
else:
    st.success("Every file looks like the updated version.")

# ---------------------------------------------------------------- 3. secrets
st.header("3. Secrets")
try:
    has_db = "database" in st.secrets and bool(st.secrets["database"].get("url"))
except Exception as exc:
    has_db = False
    st.warning(f"Couldn't read secrets: {exc}")
if has_db:
    url = str(st.secrets["database"]["url"])
    shown = url.split("@")[-1] if "@" in url else url
    st.success(f"[database] url is set — host: {shown[:80]}")
    if not url.startswith(("postgresql://", "postgres://")):
        st.error("The url should start with postgresql://")
    if "sslmode" not in url:
        st.warning("No sslmode in the url. Neon usually needs ?sslmode=require")
else:
    st.error("No [database] url in Secrets. Add:\n\n"
             '[database]\nurl = "postgresql://user:password@host/db?sslmode=require"')

# ---------------------------------------------------------------- 4. connect
st.header("4. Database connection")
if has_db:
    try:
        import psycopg
        with psycopg.connect(st.secrets["database"]["url"], connect_timeout=8) as conn:
            version = conn.execute("SELECT version()").fetchone()[0]
        st.success(f"Connected. {version[:60]}")
    except Exception as exc:
        st.error(f"Could not connect: {exc}")
        st.caption("Check the host, the password, and that the Neon project exists.")
else:
    st.info("Skipped — no url to try.")

# ---------------------------------------------------------------- 5. import
st.header("5. Importing the app")
try:
    import core  # noqa: F401
    st.success("core imported — the app's own modules are consistent.")
    try:
        core.init_db()
        st.success("Tables created or already present.")
        st.write(f"Participants currently stored: {len(core.get_students())}")
    except Exception:
        st.error("init_db() failed:")
        st.code(traceback.format_exc(), language=None)
except Exception:
    st.error("Importing the app failed — this is the crash you are seeing:")
    st.code(traceback.format_exc(), language=None)
