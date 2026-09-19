# -*- coding: utf-8 -*-
"""Who can take a part, rotation order and automatic suggestions."""
from pdfs import *  # noqa: F401,F403


# =============================================================================
# ASSIGNMENT PICKER HELPERS
# =============================================================================
def eligible_ids(role, students, show_all, away=frozenset(), suspended=frozenset()):
    active = students[(students["active"] == 1) & ~students["id"].isin(suspended)]
    if not show_all:
        active = active[~active["id"].isin(away)]
    if show_all or role not in ROLE_RULES:
        return active["id"].tolist()
    privileges, brothers_only = ROLE_RULES[role]
    mask = active["privilege_list"].apply(lambda p: bool(privileges & set(p)))
    if brothers_only:
        mask &= active["gender"] == "Brother"
    return active[mask]["id"].tolist()


def ordered_options(ids, last_dates, keep=None):
    """Least recently used first, with the current pick always included."""
    ids = list(dict.fromkeys(ids))
    if keep is not None and keep not in ids:
        ids.append(keep)
    ids.sort(key=lambda i: last_dates.get(i) or "")
    return [None] + ids


def person_label_factory(students, last_dates, away=frozenset(), role_dates=None,
                        family_of=None, suspended=frozenset(), details=None):
    """Labels for the people dropdowns.

    Each reads "🟢 Kofi Mensah — 3 weeks ago, Bible Reading": a colour for how
    long they have waited, then what they last did. The colour leads because
    the list is ordered by it, so the eye only has to go as far as the first
    green.
    """
    names = dict(zip(students["id"], students["name"]))
    inactive = set(students[students["active"] != 1]["id"])
    tags = dict(zip(students["id"], students["group_list"]))
    fam = dict(zip(students["id"], students["family"]))
    details = details or {}

    def label(pid):
        if pid is None:
            return "— Unassigned —"
        role_last = (role_dates or {}).get(pid)
        marker, wording = recency(role_last or last_dates.get(pid))
        if role_last:
            what = f"{wording}, this same part"
        else:
            entry = details.get(pid)
            what = f"{wording}, {entry[1]}" if entry and entry[1] else wording
        flags = ""
        if pid in inactive:
            flags += " · inactive"
        if pid in away:
            flags += " · away"
        if pid in suspended:
            flags += " · suspended"
        for g in tags.get(pid, []):
            flags += f" · {GROUP_TAGS[g]}"
        if family_of is not None and same_family(fam, pid, family_of):
            flags += " · family"
        return f"{marker} {names.get(pid, '?')} — {what}{flags}"

    return label


def assistant_pool(students, student_id, away, show_all=False):
    """Same category or same family (a parent can assist their child)."""
    active = students[(students["active"] == 1) & ~students["id"].isin(away)]
    pool = [p for p in active["id"].tolist() if p != student_id]
    if student_id is None or show_all:
        return pool
    cats = dict(zip(students["id"], students["gender"]))
    fam = dict(zip(students["id"], students["family"]))
    return [p for p in pool
            if cats.get(p) == cats.get(student_id) or same_family(fam, p, student_id)]


def held_recently(role_dates, pid, meeting_date, gap=SAME_ROLE_GAP_DAYS):
    """True if this person had this same part within the last `gap` days."""
    last = role_dates.get(pid)
    if not last:
        return False
    try:
        then = datetime.strptime(str(last), "%Y-%m-%d").date()
        when = datetime.strptime(str(meeting_date), "%Y-%m-%d").date()
    except ValueError:
        return False
    return 0 <= (when - then).days <= gap


def suggest_assignments(slots, students, away, meeting_date):
    """Fill each slot with the eligible person idlest for that role.

    Nobody takes the same part two meetings running — this week's chairman gets
    something else next week — unless nobody else qualifies, in which case the
    part is better filled by a repeat than left empty.
    """
    used = set()
    last_any = last_assignment_dates(meeting_date)
    picks = {}
    for i, slot in enumerate(slots):
        role_dates = last_role_dates(slot["role"])
        ids = [p for p in eligible_ids(slot["role"], students, False, away)
               if p not in used]
        rested = [p for p in ids
                  if not held_recently(role_dates, p, meeting_date)]
        ids = rested or ids           # fall back rather than leave it empty
        if not ids:
            picks[i] = (None, None)
            continue
        ids.sort(key=lambda p: (role_dates.get(p) or "", last_any.get(p) or ""))
        sid = ids[0]
        used.add(sid)
        aid = None
        if slot["needs_assistant"]:
            fam = dict(zip(students["id"], students["family"]))
            tags = dict(zip(students["id"], students["group_list"]))
            young = bool({"Child", "New student"} & set(tags.get(sid, [])))
            pool = [p for p in assistant_pool(students, sid, away) if p not in used]
            # children and new students are paired with family first
            pool.sort(key=lambda p: (not (young and same_family(fam, p, sid)),
                                     last_any.get(p) or ""))
            if pool:
                aid = pool[0]
                used.add(aid)
        picks[i] = (sid, aid)
    return picks
