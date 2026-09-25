# -*- coding: utf-8 -*-
"""Full backup and restore of every table (used by the Admin page)."""
import json

from db import *  # noqa: F401,F403
from db import (_forget_schedules, _forget_settings,  # underscored: not in *
                _forget_students, _forget_templates)

TABLES = [
    "students", "schedules", "meetings", "settings",
    "unavailable", "workbook_weeks", "audit_log", "snapshots", "templates",
    "talks",
]
BACKUP_VERSION = 1


def export_all():
    """{table: [row dicts]} for every table."""
    data = {"_version": BACKUP_VERSION,
            "_created": datetime.now().isoformat(timespec="seconds")}
    with get_conn() as conn:
        for table in TABLES:
            cols = table_columns(conn, table)
            rows = conn.execute(f"SELECT {qcols(cols)} FROM {table}").fetchall()
            data[table] = [dict(zip(cols, r)) for r in rows]
    return data


def backup_bytes():
    """The backup file, and a note of when one was last taken.

    This is the only second copy of the data now, so the dashboard reminds you
    when it has been a while.
    """
    set_setting("last_export", date.today().isoformat())
    return json.dumps(export_all(), ensure_ascii=False, indent=1).encode("utf-8")


def _clean(value):
    # A restored backup may hold blank strings for missing values.
    if value == "":
        return None
    return value


def import_all(data, log=True):
    """Replace every table with the backup's rows. Unknown columns are ignored,
    so backups from older versions of the app still load."""
    if not isinstance(data, dict) or "students" not in data:
        raise ValueError("This isn't a Meeting Scheduler backup.")
    init_db()
    counts = {}
    with get_conn() as conn:
        for table in TABLES:
            rows = data.get(table)
            if rows is None:
                continue
            cols = table_columns(conn, table)
            conn.execute(f"DELETE FROM {table}")
            for row in rows:
                keep = {k: _clean(v) for k, v in row.items() if k in cols}
                if not keep:
                    continue
                conn.execute(
                    f"INSERT INTO {table} ({qcols(keep)}) "
                    f"VALUES ({', '.join('?' for _ in keep)})",
                    list(keep.values()),
                )
            counts[table] = len(rows)
    init_db()           # upgrade anything restored from an older version
    resync_identities()  # rows came back with their own ids
    _forget_schedules()
    _forget_settings()
    _forget_students()
    _forget_templates()
    if log:
        log_change("Data restored",
                   f"{counts.get('students', 0)} participants, "
                   f"{counts.get('schedules', 0)} schedule rows")
    return counts


def is_empty():
    with get_conn() as conn:
        return all(
            conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
            for t in ("students", "schedules")
        )
