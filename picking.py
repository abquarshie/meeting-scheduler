# -*- coding: utf-8 -*-
"""Who can take a part, rotation order and automatic suggestions."""
from slips import *  # noqa: F401,F403


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


def recent_student_part(students_parts, pid, meeting_date, gap=SAME_ROLE_GAP_DAYS):
    """True if this person had any field-ministry part recently.

    The ministry parts are separate roles, so a rule about the identical part
    lets someone take Initial Presentation, then Making Disciples, then
    Explaining Your Beliefs on three consecutive weeks. For taking turns, what
    matters is that they had a student part at all.
    """
    return held_recently(students_parts, pid, meeting_date, gap)


def suggest_assignments(slots, students, away, meeting_date, skip=None):
    """Fill each slot with the eligible person idlest for that role.

    Slots are filled most-constrained first: taken in page order, an early slot
    with many candidates can take the only person qualified for a later one and
    leave that part empty. skip holds slots that already have someone, whose
    people are reserved so a suggestion cannot double-book them.

    Nobody takes the same part two meetings running — this week's chairman gets
    something else next week, and the field-ministry parts count as one for that
    purpose — unless nobody else qualifies, when filling beats leaving it empty.
    """
    used = set()
    last_any = last_assignment_dates(meeting_date)
    student_parts = last_student_part_dates(meeting_date)
    picks = {}

    # whoever is already chosen stays chosen, and is reserved so a suggestion
    # cannot hand them a second part in the same meeting
    for i, pair in (skip or {}).items():
        if i >= len(slots):
            continue
        picks[i] = None
        for pid in (pair if isinstance(pair, (tuple, list)) else (pair,)):
            if pid is not None:
                used.add(pid)
    order = sorted(
        (i for i in range(len(slots)) if i not in (skip or {})),
        key=lambda i: len(eligible_ids(slots[i]["role"], students, False, away)))

    for i in order:
        slot = slots[i]
        role_dates = last_role_dates(slot["role"])
        ids = [p for p in eligible_ids(slot["role"], students, False, away)
               if p not in used]
        if slot["student_part"]:
            rested = [p for p in ids
                      if not recent_student_part(student_parts, p, meeting_date)]
        else:
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


def create_week(meeting_date, label, week, students, aux_on, group=""):
    """Build one midweek schedule from a workbook week and fill it in.

    The monthly job was: create, fill, save, repeat. This does one week end to
    end so a whole month can be laid down in one go and then reviewed, which is
    the part that actually needs a person.
    """
    slots = apply_aux(build_midweek_slots(week["parts"]), aux_on)
    away = get_unavailable(meeting_date) | get_suspended(students, meeting_date)
    picks = suggest_assignments(slots, students, away, meeting_date)
    songs = week.get("songs") or []
    meta = {
        "heading": label,
        "book": week.get("book", ""),
        "aux": aux_on,
        "aux_group": group,
        "opening_song": songs[0] if len(songs) > 0 else "",
        "middle_song": songs[1] if len(songs) > 1 else "",
        "closing_song": songs[2] if len(songs) > 2 else "",
    }
    names = dict(zip(students["id"], students["name"]))
    save_schedule(meeting_date, MIDWEEK, slots, picks, meta, names)
    filled = sum(1 for sid, _ in picks.values() if sid)
    return filled, len(slots)
