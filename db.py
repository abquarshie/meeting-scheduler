# -*- coding: utf-8 -*-
"""SQLite storage: participants, schedules, settings."""
from contextlib import contextmanager
from datetime import date, datetime, timedelta
import json
import os
import re
import threading

import pandas as pd
import psycopg
import streamlit as st

from utils import *  # noqa: F401,F403


# =============================================================================
# DATABASE
# =============================================================================
# Postgres, so the data outlives the container. The SQL below is written with
# SQLite's "?" placeholders and translated on the way out, which keeps every
# query readable and the port reviewable. No query contains a literal "?" or
# "%", which is what makes that translation safe.


def dsn():
    """Connection string, from the app's secrets or the environment."""
    env = os.environ.get("MEETING_DSN")
    if env:
        return env
    try:
        return st.secrets["database"]["url"]
    except Exception:
        raise RuntimeError(
            "No database configured. Add a [database] url to the app's secrets "
            "(Streamlit Cloud → Settings → Secrets), or set MEETING_DSN."
        )


def schema():
    """Schema to work in. Tests point each test at its own."""
    return os.environ.get("MEETING_SCHEMA", "public")


def _sql(text):
    return text.replace("?", "%s")


class _Conn:
    """The small part of the sqlite3 connection API this app uses."""

    def __init__(self, raw):
        self._raw = raw
        self.total_changes = 0

    def execute(self, sql, params=()):
        cur = self._raw.cursor()
        cur.execute(_sql(sql), tuple(params))
        self.total_changes += max(cur.rowcount, 0)
        return cur

    def executemany(self, sql, seq):
        cur = self._raw.cursor()
        rows = [tuple(p) for p in seq]
        if rows:
            cur.executemany(_sql(sql), rows)
            self.total_changes += max(cur.rowcount, 0)
        return cur


# Fail fast and say why. Without these, a wrong password or host makes every
# page wait the full default (30s) before showing an error, which looks like
# the app failing to start rather than a setting being wrong.
CONNECT_TIMEOUT = 8     # seconds to reach the server
POOL_TIMEOUT = 10       # seconds to wait for a free connection


@st.cache_resource(show_spinner=False)
def _pool(url, schema_name):
    from psycopg_pool import ConnectionPool
    # Connect once directly first. The pool retries in the background and only
    # ever reports "couldn't get a connection after N sec", which hides the
    # reason — a wrong password, an unknown host, a missing database. A plain
    # connect surfaces the actual message from the server.
    try:
        psycopg.connect(url, connect_timeout=CONNECT_TIMEOUT).close()
    except Exception as exc:
        raise RuntimeError(f"{str(exc).strip() or exc.__class__.__name__}") from exc
    from psycopg_pool import ConnectionPool as _CP
    return ConnectionPool(
        url, min_size=1, max_size=5, open=True, timeout=POOL_TIMEOUT,
        # Neon suspends its compute when idle and terminates the connections.
        # check runs a liveness test before handing one out, so a suspended
        # database costs one reconnect instead of an AdminShutdown crash.
        check=_CP.check_connection,
        max_idle=60,        # recycle before Neon gets to them
        max_lifetime=600,
        # prepare_threshold=None turns off automatic server-side prepared
        # statements. psycopg enables them after a query repeats, which breaks
        # against a transaction-pooling proxy such as Neon's "-pooler" endpoint,
        # and only once the app has been up a while. The app has its own pool,
        # so nothing is lost by switching them off.
        kwargs={"options": f"-c search_path={schema_name}",
                "connect_timeout": CONNECT_TIMEOUT,
                "prepare_threshold": None},
    )


_local = threading.local()


def _live_connection(pool):
    """A connection proven alive, or a fresh one.

    The pool's own check is not enough here: a connection can be handed out
    healthy and be dead by the next use, and a suspended Neon compute kills
    every connection at once. Proving it before the request starts costs one
    cheap round trip and turns a crash into a reconnect.
    """
    last = None
    for _ in range(3):
        try:
            raw = pool.getconn(timeout=POOL_TIMEOUT)
        except Exception as exc:
            last = exc
            continue
        try:
            raw.execute("SELECT 1")
            return raw
        except psycopg.Error as exc:       # dead: let the pool bin it, try again
            last = exc
            try:
                raw.close()
            except Exception:
                pass
            try:
                pool.putconn(raw)
            except Exception:
                pass
    raise last if last else RuntimeError("no database connection")


@contextmanager
def get_conn():
    """A connection from the pool, reused by nested calls.

    Reentrancy matters: save_schedule() opens a connection and then calls
    log_change(), which wants one too. With a pool, letting that take a second
    connection deadlocks once every pooled connection is held by a caller
    waiting for another. Joining the outer transaction also means a change and
    its log entry commit or roll back together.
    """
    existing = getattr(_local, "conn", None)
    if existing is not None:
        yield existing
        return
    pool = _pool(dsn(), schema())
    raw = _live_connection(pool)
    conn = _Conn(raw)
    _local.conn = conn
    try:
        yield conn
        raw.commit()
    except BaseException:
        try:
            raw.rollback()
        except Exception:
            pass
        raise
    finally:
        _local.conn = None
        try:
            pool.putconn(raw)
        except Exception:
            pass
    if conn.total_changes:
        mark_dirty()


def read_df(sql, params=()):
    """A DataFrame from one query, without handing pandas the raw driver."""
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        cols = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def mark_dirty():
    """Remember that data changed so it can be copied to Google Sheets."""
    try:
        st.session_state["_db_dirty"] = True
    except Exception:  # outside a Streamlit session (tests, scripts)
        pass


def current_user():
    try:
        return st.session_state.get("user_name", "") or ""
    except Exception:
        return ""


def log_change(action, details=""):
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO audit_log (ts, "user", action, details) VALUES (?, ?, ?, ?)',
            (datetime.now().isoformat(timespec="seconds"), current_user(),
             action, details),
        )


def get_log(limit=500):
    return read_df(
        'SELECT ts, "user", action, details FROM audit_log ORDER BY id DESC LIMIT ?',
        (limit,))


def qcols(names):
    """Quote a column list for interpolation — "user" is reserved in Postgres."""
    return ", ".join(f'"{n}"' for n in names)


def table_columns(conn, table):
    return [r[0] for r in conn.execute(
        """SELECT column_name FROM information_schema.columns
            WHERE table_schema = ? AND table_name = ?
            ORDER BY ordinal_position""", (schema(), table)).fetchall()]


def _add_missing_columns(conn, table, columns):
    for name, ddl in columns.items():
        conn.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "{name}" {ddl}')


def resync_identities():
    """Move each id sequence past the largest id, after rows are restored with
    their own ids (a backup or a Sheets load)."""
    with get_conn() as conn:
        for table in ("students", "schedules", "audit_log", "snapshots"):
            conn.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")


@st.cache_resource(show_spinner=False)
def _schema_ready(schema_name, fingerprint):
    """init_db() is ~30 statements. Over a network that is seconds, so it runs
    once per process — but keyed on what init_db() actually says.

    Streamlit reruns the script when the code changes without restarting the
    process, so a cache keyed on the schema name alone survives a deploy and
    the new migrations never run: the app then queries a column that was never
    added. Hashing init_db's own source means adding a table or a column
    invalidates this automatically, with nothing to remember to bump.
    """
    init_db()
    return True


def schema_fingerprint():
    import hashlib
    import inspect
    try:
        source = inspect.getsource(init_db)
    except OSError:                                  # pragma: no cover
        return "unknown"
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]


def ensure_db():
    _schema_ready(schema(), schema_fingerprint())


def init_db():
    with get_conn() as conn:
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema()}")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                name TEXT NOT NULL,
                gender TEXT,
                privileges TEXT
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                meeting_date TEXT,
                meeting_type TEXT,
                part_name TEXT,
                assigned_person TEXT
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                meeting_date TEXT NOT NULL,
                meeting_type TEXT NOT NULL,
                heading TEXT,
                opening_song TEXT,
                middle_song TEXT,
                closing_song TEXT,
                PRIMARY KEY (meeting_date, meeting_type)
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS talks (
                number TEXT PRIMARY KEY,
                title TEXT
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                name TEXT PRIMARY KEY,
                file_name TEXT,
                data TEXT
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )""")
        # Upgrade databases created by the first version of the app.
        _add_missing_columns(conn, "students", {
            "active": "INTEGER DEFAULT 1",
            "family": "TEXT",
            "groups": "TEXT",
            "suspended": "INTEGER DEFAULT 0",
            "suspended_until": "TEXT",
        })
        _add_missing_columns(conn, "schedules", {
            "part_no": "INTEGER",
            "minutes": "INTEGER",
            "section": "TEXT",
            "role": "TEXT",
            "student_part": "INTEGER DEFAULT 0",
            "needs_assistant": "INTEGER DEFAULT 0",
            "student_id": "INTEGER",
            "assistant_id": "INTEGER",
            "assistant_name": "TEXT",
            "sort_order": "INTEGER DEFAULT 0",
            "hall": "TEXT DEFAULT 'main_hall'",
            "visitor": "TEXT",
        })
        _add_missing_columns(conn, "meetings", {
            "aux": "INTEGER",
            "book": "TEXT",
            "aux_group": "TEXT",
            "talk_number": "TEXT",
            "talk_title": "TEXT",
        })
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                ts TEXT, "user" TEXT, action TEXT, details TEXT
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workbook_weeks (
                label TEXT PRIMARY KEY,
                position INTEGER,
                data TEXT
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                ts TEXT, "user" TEXT, reason TEXT,
                meeting_date TEXT, meeting_type TEXT, data TEXT
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS unavailable (
                student_id INTEGER NOT NULL,
                meeting_date TEXT NOT NULL,
                PRIMARY KEY (student_id, meeting_date)
            )""")
        conn.execute("UPDATE schedules SET hall = 'main_hall' WHERE hall IS NULL")
        conn.execute("UPDATE students SET active = 1 WHERE active IS NULL")
        conn.execute("""
            UPDATE schedules
               SET student_id = (SELECT s.id FROM students s
                                  WHERE s.name = schedules.assigned_person LIMIT 1)
             WHERE student_id IS NULL AND assigned_person IS NOT NULL""")
        legacy = conn.execute(
            "SELECT id, part_name, meeting_type FROM schedules WHERE role IS NULL"
        ).fetchall()
        for row_id, part_name, meeting_type in legacy:
            role = infer_role(part_name)
            section = default_section(role, meeting_type)
            if role == "Prayer" and meeting_type != WEEKEND:
                section = "Closing" if "clos" in (part_name or "").lower() else "Opening"
            conn.execute(
                """UPDATE schedules SET role = ?, section = COALESCE(section, ?),
                       student_part = ?, needs_assistant = ?, sort_order = id
                   WHERE id = ?""",
                (role, section, int(role in STUDENT_ROLES),
                 int(role in ASSISTANT_ROLES), row_id),
            )
        # the weekend meeting has its own chairman role
        conn.execute("""UPDATE schedules SET role = 'Weekend Chairman'
                         WHERE meeting_type = ? AND role = 'Chairman'""", (WEEKEND,))


@st.cache_data(show_spinner=False)
def _all_settings(schema_name):
    with get_conn() as conn:
        return dict(conn.execute("SELECT key, value FROM settings").fetchall())


def get_setting(key, default=""):
    """Settings are read many times per page (wording, meeting days, flags), so
    fetch the table once and serve every lookup from it."""
    value = _all_settings(schema()).get(key)
    return default if value is None else value


def _forget_settings():
    _all_settings.clear()


def get_setting_uncached(key, default=""):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
    _forget_settings()


def get_students(active_only=False):
    query = ("SELECT id, name, gender, privileges, active, family, groups, "
             "suspended, suspended_until FROM students")
    if active_only:
        query += " WHERE active = 1"
    df = read_df(query + " ORDER BY lower(name)")
    def text(v):
        return v if isinstance(v, str) else ""

    df["privilege_list"] = df["privileges"].apply(lambda v: parse_privileges(text(v)))
    df["group_list"] = df["groups"].apply(
        lambda v: [g.strip() for g in text(v).split(",") if g.strip() in GROUPS])
    df["family"] = pd.Series([nfc(text(v)) or None for v in df["family"]],
                             index=df.index, dtype=object)
    return df


def family_names(students):
    return sorted({f for f in students["family"] if f}, key=str.lower)


def same_family(fam, a, b):
    return bool(a is not None and b is not None and fam.get(a) and fam.get(a) == fam.get(b))


def pick_family(label_prefix, existing, current, key):
    """Choose an existing family or type a new one. Returns the family name or None."""
    options = [NO_FAMILY] + existing
    idx = options.index(current) if current in options else 0
    chosen = st.selectbox(f"{label_prefix}Family", options, index=idx, key=f"{key}_sel")
    new = st.text_input("…or start a new family", key=f"{key}_new",
                        placeholder="e.g. Mensah family")
    if nfc(new):
        return apply_ga_substitutes(nfc(new))
    return None if chosen == NO_FAMILY else chosen


def add_student(name, gender, privileges, family=None, groups=()):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO students (name, gender, privileges, active, family, groups)
               VALUES (?, ?, ?, 1, ?, ?)""",
            (apply_ga_substitutes(nfc(name)), gender, ", ".join(privileges),
             family, ", ".join(groups)),
        )
    log_change("Participant added", nfc(name))


def update_student(student_id, name, gender, privileges, active, family=None, groups=()):
    with get_conn() as conn:
        conn.execute(
            """UPDATE students SET name = ?, gender = ?, privileges = ?, active = ?,
                   family = ?, groups = ? WHERE id = ?""",
            (apply_ga_substitutes(nfc(name)), gender, ", ".join(privileges),
             int(active), family, ", ".join(groups), student_id),
        )
        # keep the name snapshot on old schedules in step with the rename
        conn.execute("UPDATE schedules SET assigned_person = ? WHERE student_id = ?",
                     (apply_ga_substitutes(nfc(name)), student_id))
        conn.execute("UPDATE schedules SET assistant_name = ? WHERE assistant_id = ?",
                     (apply_ga_substitutes(nfc(name)), student_id))
    log_change("Participant edited", f"{nfc(name)} (active={bool(active)})")


def student_usage_count(student_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM schedules WHERE student_id = ? OR assistant_id = ?",
            (student_id, student_id),
        ).fetchone()[0]


def delete_student(student_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    log_change("Participant deleted", f"id {student_id}")


def get_schedules():
    df = read_df(
            """
            SELECT sc.id, sc.meeting_date, sc.meeting_type, sc.part_no, sc.part_name,
                   sc.minutes, sc.section, sc.role, sc.student_part, sc.needs_assistant,
                   sc.student_id, sc.assistant_id, sc.sort_order,
                   COALESCE(sc.hall, 'main_hall') AS hall, sc.visitor,
                   COALESCE(sc.visitor, s.name, sc.assigned_person) AS person,
                   COALESCE(a.name, sc.assistant_name) AS assistant
              FROM schedules sc
              LEFT JOIN students s ON s.id = sc.student_id
              LEFT JOIN students a ON a.id = sc.assistant_id
             ORDER BY sc.meeting_date DESC, sc.meeting_type, sc.sort_order, sc.id
            """)
    # NaN is truthy, so turn missing names into None for simple `or` checks.
    for col in ("person", "assistant"):
        df[col] = df[col].astype(object).where(df[col].notna(), None)
    return df


@st.cache_data(show_spinner=False)
def _talks(schema_name):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT number, title FROM talks").fetchall()
    # numeric where it can be, so 2 sorts before 10
    def key(pair):
        try:
            return (0, int(pair[0]), "")
        except ValueError:
            return (1, 0, str(pair[0]))
    return [(n, t) for n, t in sorted(rows, key=key)]


def get_talks():
    """The congregation's list of public talks, as (number, title)."""
    return _talks(schema())


def talk_label(number, title):
    number, title = nfc(str(number)), nfc(title or "")
    return f"No. {number} — {title}" if title else f"No. {number}"


def save_talk(number, title):
    number = nfc(str(number))
    if not number:
        raise ValueError("A talk needs a number.")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO talks (number, title) VALUES (?, ?) "
            "ON CONFLICT(number) DO UPDATE SET title = excluded.title",
            (number, nfc(title)))
    _talks.clear()
    log_change("Public talk saved", talk_label(number, title))


def import_talks(rows, replace=False):
    """Load talks in bulk from (number, title) pairs.

    Two hundred outlines is not a thing to type into a table one row at a time,
    and a correction should be a re-import rather than a hunt.
    """
    clean = []
    seen = set()
    for number, title in rows:
        number = nfc(str(number or "")).strip()
        if not number or number in seen:
            continue
        seen.add(number)
        clean.append((number, nfc(title or "")))
    if not clean:
        return 0, 0
    before = {n for n, _ in get_talks()}
    with get_conn() as conn:
        if replace:
            conn.execute("DELETE FROM talks")
        conn.executemany(
            "INSERT INTO talks (number, title) VALUES (?, ?) "
            "ON CONFLICT(number) DO UPDATE SET title = excluded.title", clean)
    _talks.clear()
    added = len([n for n, _ in clean if n not in before])
    log_change("Public talks imported",
               f"{len(clean)} talk(s), {added} new")
    return len(clean), added


def delete_talk(number):
    with get_conn() as conn:
        conn.execute("DELETE FROM talks WHERE number = ?", (nfc(str(number)),))
    _talks.clear()
    log_change("Public talk removed", f"No. {number}")


def save_template(name, file_name, raw):
    """Store a blank form (the official S-89) so printing is one click."""
    import base64
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO templates (name, file_name, data) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET file_name = excluded.file_name, "
            "data = excluded.data",
            (name, file_name, base64.b64encode(raw).decode("ascii")))
    _forget_templates()
    log_change("Blank form saved", f"{name}: {file_name}")


def delete_template(name):
    with get_conn() as conn:
        conn.execute("DELETE FROM templates WHERE name = ?", (name,))
    _forget_templates()
    log_change("Blank form removed", name)


@st.cache_data(show_spinner=False)
def _templates(schema_name):
    with get_conn() as conn:
        rows = conn.execute("SELECT name, file_name, data FROM templates").fetchall()
    return {name: (file_name, data) for name, file_name, data in rows}


def _forget_templates():
    _templates.clear()


def load_template(name):
    """(bytes, file name) for a stored blank form, or (None, "")."""
    import base64
    entry = _templates(schema()).get(name)
    if not entry:
        return None, ""
    file_name, data = entry
    try:
        return base64.b64decode(data), file_name
    except Exception:
        return None, ""


def template_names():
    return sorted(_templates(schema()))


def fill_counts(rows):
    """(filled, needed) for a set of schedule rows: a part plus, where the part
    calls for one, its assistant."""
    needed = len(rows) + int((rows["needs_assistant"] == 1).sum())
    filled = int(rows["person"].notna().sum()) + int(
        ((rows["needs_assistant"] == 1) & rows["assistant"].notna()).sum())
    return filled, needed


def open_slots(rows):
    filled, needed = fill_counts(rows)
    return needed - filled


def saved_meetings(schedules_df):
    """[(date, type), ...] newest first."""
    if schedules_df.empty:
        return []
    pairs = schedules_df[["meeting_date", "meeting_type"]].drop_duplicates()
    return list(pairs.itertuples(index=False, name=None))


def meeting_label(pair):
    return f"{fmt_date(pair[0])} · {pair[1]}"


def load_schedule(meeting_date, meeting_type, schedules_df=None):
    df = get_schedules() if schedules_df is None else schedules_df
    rows = df[(df["meeting_date"] == str(meeting_date)) & (df["meeting_type"] == meeting_type)]
    slots, picks, visitors = [], {}, {}
    for _, r in rows.iterrows():
        role = r["role"] or infer_role(r["part_name"])
        part_no = int(r["part_no"]) if pd.notna(r["part_no"]) else None
        minutes = int(r["minutes"]) if pd.notna(r["minutes"]) else None
        section = r["section"] or default_section(role, meeting_type)
        slot = make_slot(r["part_name"], role, section, part_no, minutes, r["hall"])
        slot["allow_visitor"] = visitor_allowed(role, r["part_name"],
                                                r["section"])
        slots.append(slot)
        sid = int(r["student_id"]) if pd.notna(r["student_id"]) else None
        aid = int(r["assistant_id"]) if pd.notna(r["assistant_id"]) else None
        picks[slot_match_key(slot)] = (sid, aid)
        if pd.notna(r.get("visitor")) and r.get("visitor"):
            visitors[slot_match_key(slot)] = r["visitor"]
    return slots, picks, visitors


def get_meeting_meta(meeting_date, meeting_type):
    with get_conn() as conn:
        row = conn.execute(
            """SELECT heading, opening_song, middle_song, closing_song, aux,
                      talk_number, talk_title, book, aux_group FROM meetings
               WHERE meeting_date = ? AND meeting_type = ?""",
            (str(meeting_date), meeting_type),
        ).fetchone()
    keys = ["heading", "opening_song", "middle_song", "closing_song", "aux",
            "talk_number", "talk_title", "book", "aux_group"]
    meta = dict(zip(keys, row)) if row else {k: "" for k in keys}
    if not row:
        meta["aux"] = None
    for k in ("heading", "opening_song", "middle_song", "closing_song",
              "talk_number", "talk_title", "book", "aux_group"):
        meta[k] = meta.get(k) or ""
    return meta


def talk_text(meta):
    """'No. 12 — “Title”' or whichever part is filled in."""
    parts = []
    if meta.get("talk_number"):
        parts.append(f"No. {meta['talk_number']}")
    if meta.get("talk_title"):
        parts.append(f"“{meta['talk_title']}”")
    return " — ".join(parts)


MAX_SNAPSHOTS = 40  # keep the history small enough to sync and restore cheaply


def _take_snapshot(conn, meeting_date, meeting_type, reason):
    """Store what's currently saved for this meeting so a save can be undone.

    Called inside an open connection, before the rows are replaced. Saving a
    meeting that has nothing stored yet records an empty snapshot, so undoing
    a first save removes it again rather than leaving it half-there.
    """
    sched_cols = table_columns(conn, "schedules")
    meet_cols = table_columns(conn, "meetings")
    rows = conn.execute(
        f"SELECT {qcols(sched_cols)} FROM schedules "
        "WHERE meeting_date = ? AND meeting_type = ? ORDER BY sort_order, id",
        (str(meeting_date), meeting_type)).fetchall()
    meeting = conn.execute(
        f"SELECT {qcols(meet_cols)} FROM meetings "
        "WHERE meeting_date = ? AND meeting_type = ?",
        (str(meeting_date), meeting_type)).fetchone()
    data = {
        "schedules": [dict(zip(sched_cols, r)) for r in rows],
        "meeting": dict(zip(meet_cols, meeting)) if meeting else None,
    }
    conn.execute(
        '''INSERT INTO snapshots (ts, "user", reason, meeting_date, meeting_type, data)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (datetime.now().isoformat(timespec="seconds"), current_user(), reason,
         str(meeting_date), meeting_type, json.dumps(data, ensure_ascii=False)))
    conn.execute(
        "DELETE FROM snapshots WHERE id NOT IN "
        "(SELECT id FROM snapshots ORDER BY id DESC LIMIT ?)", (MAX_SNAPSHOTS,))


def last_snapshot(meeting_date, meeting_type):
    """The most recent undo point for this meeting: (id, ts, user, reason, rows)."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT id, ts, user, reason, data FROM snapshots
               WHERE meeting_date = ? AND meeting_type = ?
               ORDER BY id DESC LIMIT 1""",
            (str(meeting_date), meeting_type)).fetchone()
    if not row:
        return None
    data = json.loads(row[4])
    return {"id": row[0], "ts": row[1], "user": row[2], "reason": row[3],
            "rows": len(data["schedules"]),
            "assigned": sum(1 for r in data["schedules"] if r.get("student_id"))}


def undo_last(meeting_date, meeting_type):
    """Put back what was stored before the last save or delete.

    The current state is snapshotted first, so undo can itself be undone.
    Returns the number of assignment rows restored, or None when there is
    nothing to undo.
    """
    with get_conn() as conn:
        row = conn.execute(
            """SELECT id, data FROM snapshots
               WHERE meeting_date = ? AND meeting_type = ?
               ORDER BY id DESC LIMIT 1""",
            (str(meeting_date), meeting_type)).fetchone()
        if not row:
            return None
        snap_id, data = row[0], json.loads(row[1])
        _take_snapshot(conn, meeting_date, meeting_type, "before undo")
        conn.execute("DELETE FROM snapshots WHERE id = ?", (snap_id,))
        conn.execute("DELETE FROM schedules WHERE meeting_date = ? AND meeting_type = ?",
                     (str(meeting_date), meeting_type))
        conn.execute("DELETE FROM meetings WHERE meeting_date = ? AND meeting_type = ?",
                     (str(meeting_date), meeting_type))
        for r in data["schedules"]:
            keep = {k: v for k, v in r.items() if k != "id"}
            conn.execute(
                f"INSERT INTO schedules ({qcols(keep)}) "
                f"VALUES ({', '.join('?' for _ in keep)})", list(keep.values()))
        if data["meeting"]:
            keep = data["meeting"]
            conn.execute(
                f"INSERT INTO meetings ({qcols(keep)}) "
                f"VALUES ({', '.join('?' for _ in keep)})", list(keep.values()))
    restored = len(data["schedules"])
    _forget_schedules()
    log_change("Save undone", f"{meeting_type} {meeting_date}: {restored} row(s) put back")
    return restored


def save_schedule(meeting_date, meeting_type, slots, picks, meta, names):
    """Replace everything stored for this date + meeting type."""
    rows = []
    for order, slot in enumerate(slots):
        sid, aid = picks.get(order, (None, None))
        rows.append((
            str(meeting_date), meeting_type, slot["part_no"], slot["title"],
            slot.get("minutes"), slot["section"], slot["role"],
            int(slot["student_part"]), int(slot["needs_assistant"]),
            sid, names.get(sid), aid, names.get(aid), order,
            slot.get("hall") or MAIN_HALL, picks.get(order + 10000) or None,
        ))
    with get_conn() as conn:
        _take_snapshot(conn, meeting_date, meeting_type, "before save")
        conn.execute("DELETE FROM schedules WHERE meeting_date = ? AND meeting_type = ?",
                     (str(meeting_date), meeting_type))
        conn.executemany(
            """INSERT INTO schedules (meeting_date, meeting_type, part_no, part_name,
                   minutes, section, role, student_part, needs_assistant, student_id,
                   assigned_person, assistant_id, assistant_name, sort_order, hall, visitor)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.execute(
            """INSERT INTO meetings (meeting_date, meeting_type, heading, opening_song,
                   middle_song, closing_song, aux, talk_number, talk_title, book,
                   aux_group)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(meeting_date, meeting_type) DO UPDATE SET
                   heading = excluded.heading, opening_song = excluded.opening_song,
                   middle_song = excluded.middle_song, closing_song = excluded.closing_song,
                   aux = excluded.aux, talk_number = excluded.talk_number,
                   talk_title = excluded.talk_title, book = excluded.book,
                   aux_group = excluded.aux_group""",
            (str(meeting_date), meeting_type, meta.get("heading", ""),
             meta.get("opening_song", ""), meta.get("middle_song", ""),
             meta.get("closing_song", ""), int(bool(meta.get("aux"))),
             meta.get("talk_number", ""), meta.get("talk_title", ""),
             meta.get("book", ""), meta.get("aux_group", "")),
        )
    _forget_schedules()
    log_change("Schedule saved", f"{meeting_type} {meeting_date}: "
               f"{sum(1 for v in picks.values() if isinstance(v, tuple) and v[0])} assigned")


def delete_schedule(meeting_date, meeting_type):
    with get_conn() as conn:
        _take_snapshot(conn, meeting_date, meeting_type, "before delete")
        conn.execute("DELETE FROM schedules WHERE meeting_date = ? AND meeting_type = ?",
                     (str(meeting_date), meeting_type))
        conn.execute("DELETE FROM meetings WHERE meeting_date = ? AND meeting_type = ?",
                     (str(meeting_date), meeting_type))
    _forget_schedules()
    log_change("Schedule deleted", f"{meeting_type} {meeting_date}")


def last_assignments(exclude_date):
    """student_id -> (date, part name, role) of their most recent assignment.

    The date alone doesn't tell the person scheduling what someone last did,
    which is what decides whether they are due this part or a different one.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT ON (pid) pid, meeting_date, part_name, role FROM (
                   SELECT student_id AS pid, meeting_date, part_name, role
                     FROM schedules
                    WHERE student_id IS NOT NULL AND meeting_date != ?
                   UNION ALL
                   SELECT assistant_id, meeting_date, part_name, role
                     FROM schedules
                    WHERE assistant_id IS NOT NULL AND meeting_date != ?
               ) recent
               ORDER BY pid, meeting_date DESC""",
            (str(exclude_date), str(exclude_date)),
        ).fetchall()
    return {pid: (date_, part, role) for pid, date_, part, role in rows}


def last_assignment_details(exclude_date):
    """student_id -> (date, what it was) for their most recent assignment.

    "Bible Reading, 3 weeks ago" says more than a date on its own when you are
    deciding who to give a part to.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT pid, meeting_date, part_name, role, assisted FROM (
                   SELECT student_id AS pid, meeting_date, part_name, role, 0 AS assisted
                     FROM schedules
                    WHERE student_id IS NOT NULL AND meeting_date != ?
                   UNION ALL
                   SELECT assistant_id, meeting_date, part_name, role, 1
                     FROM schedules
                    WHERE assistant_id IS NOT NULL AND meeting_date != ?
               ) AS everything
               ORDER BY meeting_date DESC""",
            (str(exclude_date), str(exclude_date)),
        ).fetchall()
    out = {}
    for pid, when, part_name, role, assisted in rows:
        if pid in out:                      # already have this person's latest
            continue
        what = (role or part_name or "").strip()
        out[pid] = (when, f"assisted, {what}" if assisted else what)
    return out


def last_assignment_dates(exclude_date):
    """student_id -> most recent meeting date they had a part or assisted."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT pid, MAX(meeting_date) FROM (
                   SELECT student_id AS pid, meeting_date FROM schedules
                    WHERE student_id IS NOT NULL AND meeting_date != ?
                   UNION ALL
                   SELECT assistant_id, meeting_date FROM schedules
                    WHERE assistant_id IS NOT NULL AND meeting_date != ?
               ) GROUP BY pid""",
            (str(exclude_date), str(exclude_date)),
        ).fetchall()
    return {pid: d for pid, d in rows}


@st.cache_data(show_spinner=False)
def _role_dates(schema_name):
    """{role: {student_id: last date}} for every role, in one query.

    The schedule page asks for this once per slot — a dozen round trips for one
    page render. Cleared by _forget_schedules() on every write, so it cannot
    serve stale rotation order. A change-token query was the obvious
    alternative, but that costs one round trip per call and saves nothing.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT role, student_id, MAX(meeting_date) FROM schedules
                WHERE student_id IS NOT NULL
                GROUP BY role, student_id""").fetchall()
    out = {}
    for role, pid, last in rows:
        out.setdefault(role, {})[pid] = last
    return out


def _forget_schedules():
    """Call after anything that changes the schedules table."""
    _role_dates.clear()
    _student_part_dates.clear()


@st.cache_data(show_spinner=False)
def _student_part_dates(schema_name):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT pid, MAX(meeting_date) FROM (
                   SELECT student_id AS pid, meeting_date, role FROM schedules
                    WHERE student_id IS NOT NULL
                   UNION ALL
                   SELECT assistant_id, meeting_date, role FROM schedules
                    WHERE assistant_id IS NOT NULL
               ) AS everything
               WHERE role = ANY(%s)
               GROUP BY pid""",
            (list(STUDENT_ROLES),)).fetchall()
    return {pid: when for pid, when in rows}


def last_student_part_dates(exclude_date=None):
    """student_id -> when they last had any field-ministry part or assisted.

    The ministry parts are separate roles, so "not the same part twice" lets
    someone take a different one each week. Turn-taking needs them counted
    together.
    """
    return _student_part_dates(schema())


def last_role_dates(role):
    """student_id -> most recent date they had this same role (either hall)."""
    return _role_dates(schema()).get(role, {})


def role_history(student_id, limit=8):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT meeting_date,
                      CASE WHEN assistant_id = ? AND COALESCE(student_id, -1) != ?
                           THEN part_name || ' (assistant)' ELSE part_name END,
                      hall
                 FROM schedules
                WHERE student_id = ? OR assistant_id = ?
                ORDER BY meeting_date DESC LIMIT ?""",
            (student_id, student_id, student_id, student_id, limit),
        ).fetchall()
    return rows


def is_suspended(row, on_date):
    """Suspended with no end date, or the end date hasn't passed yet."""
    if not row.get("suspended") or pd.isna(row.get("suspended")):
        return False
    until = row.get("suspended_until")
    if not isinstance(until, str) or not until:
        return True
    return str(on_date) <= until


def get_suspended(students, on_date):
    return {int(r["id"]) for r in students.to_dict("records") if is_suspended(r, on_date)}


def suspension_text(row, today=None):
    today = today or date.today().isoformat()
    if not is_suspended(row, today):
        return ""
    until = row.get("suspended_until")
    return f"Suspended until {fmt_date(until)}" if isinstance(until, str) and until \
        else "Suspended"


def set_suspension(student_id, suspended, until=None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE students SET suspended = ?, suspended_until = ? WHERE id = ?",
            (int(suspended), until if suspended else None, student_id),
        )
    log_change("Suspension " + ("set" if suspended else "lifted"),
               f"id {student_id}" + (f" until {until}" if until else ""))


def upcoming_assignments(student_id, until=None):
    today = date.today().isoformat()
    query = """SELECT meeting_date, meeting_type, part_name FROM schedules
                WHERE (student_id = ? OR assistant_id = ?) AND meeting_date >= ?"""
    params = [student_id, student_id, today]
    if until:
        query += " AND meeting_date <= ?"
        params.append(until)
    with get_conn() as conn:
        return conn.execute(query + " ORDER BY meeting_date", params).fetchall()


def get_unavailable_between(start, end):
    """Everyone away on any date in the range. The dashboard needs a whole
    week, which was seven separate queries."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT student_id FROM unavailable WHERE meeting_date BETWEEN ? AND ?",
            (str(start), str(end)),
        ).fetchall()
    return {r[0] for r in rows}


def get_unavailable(meeting_date):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT student_id FROM unavailable WHERE meeting_date = ?",
            (str(meeting_date),),
        ).fetchall()
    return {r[0] for r in rows}


def unavailable_dates(student_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT meeting_date FROM unavailable WHERE student_id = ? ORDER BY meeting_date",
            (student_id,),
        ).fetchall()
    return [r[0] for r in rows]


def away_summary(dates):
    """Collapse consecutive days into ranges: '3–9 Oct, 20 Oct'."""
    days = sorted(datetime.strptime(d, "%Y-%m-%d").date() for d in dates)
    ranges, start, prev = [], None, None
    for d in days + [None]:
        if start is None:
            start = prev = d
        elif d is not None and (d - prev).days == 1:
            prev = d
        else:
            ranges.append(fmt_date(start.isoformat(), short=True) if start == prev else
                          f"{fmt_date(start.isoformat(), short=True)}–"
                          f"{fmt_date(prev.isoformat(), short=True)}")
            start = prev = d
    return ", ".join(ranges)


def set_unavailable(student_id, dates):
    with get_conn() as conn:
        conn.execute("DELETE FROM unavailable WHERE student_id = ?", (student_id,))
        conn.executemany(
            "INSERT INTO unavailable (student_id, meeting_date) VALUES (?, ?)",
            [(student_id, str(d)) for d in dates],
        )
    log_change("Away dates changed", f"id {student_id}: {len(dates)} day(s)")


# Typists substitute 3 ) N for ɛ ɔ ŋ when the keyboard lacks them.
GA_SUBSTITUTES = {"3": "ɛ", ")": "ɔ", "N": "ŋ"}


def apply_ga_substitutes(text):
    if not get_setting("ga_convert", "0") == "1":
        return text
    out = []
    for ch in text or "":
        # only convert a capital N between letters, so real initials survive
        if ch == "N":
            out.append(ch)
        else:
            out.append(GA_SUBSTITUTES.get(ch, ch))
    result = "".join(out)
    # standalone N -> ŋ only when clearly mid-word (letter on both sides)
    result = re.sub(r"(?<=[A-Za-zɛɔŋ])N(?=[a-zɛɔŋ])", "ŋ", result)
    return result
