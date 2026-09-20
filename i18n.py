# -*- coding: utf-8 -*-
"""Interface wording. English is built in; Ga wording is typed in on the Admin page."""
from auth import *  # noqa: F401,F403

UI_TEXT = {
    "app_name": "Meeting Scheduler",
    "app_tagline": "Life and Ministry assignments",
    "nav_home": "Home",
    "nav_month": "Month overview",
    "nav_schedule": "Create or edit",
    "nav_view": "Slips and printing",
    "nav_participants": "Participants",
    "nav_workbook": "Workbook PDF",
    "nav_reports": "Reports",
    "nav_admin": "Admin",
    "h_participants": "Participants",
    "sub_participants": "Who can take which parts, families, away dates and suspensions.",
    "h_schedule": "Create or edit a schedule",
    "sub_schedule": "Pick a date, then fill each part. Only eligible people are listed.",
    "h_view": "Slips and printing",
    "sub_view": "Slips, schedule sheets, the CSV and the S-140 — for one meeting or a whole month.",
    "h_workbook": "Workbook PDF",
    "sub_workbook": "Upload the meeting workbook so each week gets its real parts.",
    "h_month": "Month overview",
    "sub_month": "Every meeting this month, what is still open, and month-wide printing.",
    "h_reports": "Reports",
    "sub_reports": "How often each person had a part, to spot anyone left out.",
    "h_admin": "Admin",
    "sub_admin": "Backups, Google Sheets, meeting days, wording and the change log.",
    "save_schedule": "Save schedule",
    "suggest": "Suggest",
    "slip_language": "Slip language",
    "settings": "Settings",
}


def tr(key):
    """Interface text. The interface is English only; Ga appears on the printed
    slips, schedule and S-140, chosen with the slip-language setting."""
    return UI_TEXT.get(key, key)
