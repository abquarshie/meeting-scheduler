# -*- coding: utf-8 -*-
"""Who can take a part, rotation order and automatic suggestions."""
from datetime import datetime

from constants import CONFLICT, GROUP_TAGS, MIDWEEK, ROLES, SISTER_ROLES
from db import (
    get_outgoing_on,
    get_suspended,
    get_unavailable,
    last_assignment_dates,
    last_role_dates,
    last_student_part_dates,
    next_role_dates,
    next_student_part_dates,
    same_family,
    same_role_gap_days,
    save_schedule,
)
from parts import build_midweek_slots
from utils import apply_aux, as_date, recency, relative_week, slot_label, weeks_apart


# =============================================================================
# ASSIGNMENT PICKER HELPERS
# =============================================================================
def eligible_ids(role, students, away=frozenset(), suspended=frozenset()):
    """Who may take this part: active, available, and qualified for the role.

    There used to be a "show everyone" switch that set all three aside at once.
    If somebody genuinely qualifies, that belongs in their privileges, not in a
    checkbox that defeats the rules on the day.
    """
    active = students[(students["active"] == 1) & ~students["id"].isin(suspended)]
    active = active[~active["id"].isin(away)]
    if role not in ROLES:
        return active["id"].tolist()
    mask = active["privilege_list"].apply(lambda p: role in p)
    if role not in SISTER_ROLES:
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
                        family_of=None, suspended=frozenset(), details=None,
                        meeting_date=None, role=None, outgoing=frozenset(),
                        elsewhere=None, upcoming=None):
    """Labels for the people dropdowns.

    Each reads "🟢 Kofi Mensah — 3 weeks ago, Bible Reading": a colour for how
    long they have waited, then what they last did. The colour leads because
    the list is ordered by it, so the eye only has to go as far as the first
    green.

    `role` lets the Watchtower Conductor skip the recency marker entirely:
    only one or two people ever take that part, so a rotation colour would
    misread as a warning where none is intended.

    `elsewhere` ({person: [parts]}) is who already has another part in this
    same meeting: they turn orange and say where, so a double booking shows
    before it is made. `upcoming` ({person: (date, what)}) is each person's
    next assignment after this meeting, named when it falls this week or next.
    """
    names = dict(zip(students["id"], students["name"]))
    inactive = set(students[students["active"] != 1]["id"])
    tags = dict(zip(students["id"], students["group_list"]))
    fam = dict(zip(students["id"], students["family"]))
    details = details or {}
    elsewhere = elsewhere or {}
    upcoming = upcoming or {}
    no_recency = role == "Watchtower Conductor"

    def label(pid):
        if pid is None:
            return "— Unassigned —"
        flags = ""
        if pid in inactive:
            flags += " · inactive"
        if pid in away:
            flags += " · away"
        if pid in outgoing:
            flags += " · going out"
        if pid in suspended:
            flags += " · suspended"
        for g in tags.get(pid, []):
            flags += f" · {GROUP_TAGS[g]}"
        if family_of is not None and same_family(fam, pid, family_of):
            flags += " · family"
        if pid in elsewhere:
            flags += " · also on " + ", ".join(elsewhere[pid])
        nxt = upcoming.get(pid)
        if nxt and meeting_date and weeks_apart(meeting_date, nxt[0]) <= 1:
            when = as_date(nxt[0])
            flags += (f" · {nxt[1]} {relative_week(when, meeting_date)}"
                      f" ({when.day} {when:%b})").replace(" this week", " later this week")
        if no_recency:
            return f"{names.get(pid, '?')}{flags}"
        role_last = (role_dates or {}).get(pid)
        marker, wording = recency(role_last or last_dates.get(pid), meeting_date)
        if role_last:
            what = f"{wording}, this same part"
        else:
            entry = details.get(pid)
            what = f"{wording}, {entry[1]}" if entry and entry[1] else wording
        if pid in elsewhere:
            marker = CONFLICT[0]            # a clash in this meeting outranks rotation
        return f"{marker} {names.get(pid, '?')} — {what}{flags}"

    return label


def assistant_pool(students, student_id, away):
    """Same category or same family (a parent can assist their child)."""
    active = students[(students["active"] == 1) & ~students["id"].isin(away)]
    pool = [p for p in active["id"].tolist() if p != student_id]
    if student_id is None:
        return pool
    cats = dict(zip(students["id"], students["gender"]))
    fam = dict(zip(students["id"], students["family"]))
    return [p for p in pool
            if cats.get(p) == cats.get(student_id) or same_family(fam, p, student_id)]


def held_recently(role_dates, pid, meeting_date, gap=None):
    """True if this person had this same part within the last `gap` days.

    `gap` defaults to the congregation's rest period (Admin → Settings),
    resolved here rather than at import time so a change to the setting
    takes effect immediately.
    """
    if gap is None:
        gap = same_role_gap_days()
    last = role_dates.get(pid)
    if not last:
        return False
    try:
        then = datetime.strptime(str(last), "%Y-%m-%d").date()
        when = datetime.strptime(str(meeting_date), "%Y-%m-%d").date()
    except ValueError:
        return False
    return 0 <= (when - then).days <= gap


def held_close(before, after, pid, meeting_date, gap=None):
    """True if this person has the part within the rest period on either
    side of this meeting: last week, or already next week. Filling Week 3
    after Week 4 is saved must respect Week 4 as much as Week 2."""
    if held_recently(before, pid, meeting_date, gap):
        return True
    if gap is None:
        gap = same_role_gap_days()
    nxt = as_date(after.get(pid)) if after.get(pid) else None
    when = as_date(meeting_date)
    return bool(nxt and when and 0 < (nxt - when).days <= gap)


def recent_student_part(students_parts, pid, meeting_date, gap=None):
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
    student_before = last_student_part_dates(meeting_date)
    student_after = next_student_part_dates(meeting_date)
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
    # most constrained first; parts a visitor can take (the public talk) last,
    # since a guest can fill them and a brother can't be borrowed back
    order = sorted(
        (i for i in range(len(slots)) if i not in (skip or {})),
        key=lambda i: (bool(slots[i].get("allow_visitor")),
                       len(eligible_ids(slots[i]["role"], students, away))))

    for i in order:
        slot = slots[i]
        role_dates = last_role_dates(slot["role"], meeting_date)
        role_after = next_role_dates(slot["role"], meeting_date)
        ids = [p for p in eligible_ids(slot["role"], students, away)
               if p not in used]
        if slot["role"] == "Watchtower Conductor":
            # only one or two people ever take this part — "held it last
            # week" isn't a reason to look elsewhere for this one.
            pass
        elif slot["student_part"]:
            rested = [p for p in ids
                      if not held_close(student_before, student_after, p, meeting_date)]
            ids = rested or ids           # fall back rather than leave it empty
        else:
            rested = [p for p in ids
                      if not held_close(role_dates, role_after, p, meeting_date)]
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
    away = (get_unavailable(meeting_date) | get_suspended(students, meeting_date)
            | get_outgoing_on(meeting_date))
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


def assignment_issues(slots, picks, students, meeting_date, meeting_type,
                      suspended=frozenset(), other_meeting=None):
    """Everything worth flagging about one meeting's picks, as
    [{"level": "error" | "warning", "slots": [index, ...], "text": "..."}].

    The Schedule page calls this on every change (so a clash shows the moment
    it is made) and again on Save (so what blocks a save is exactly what was
    shown). It only compares the picks with one another, with other meetings'
    saved assignments, and with the people's records — never with this
    meeting's own saved copy, so saving again unchanged raises nothing new.

    other_meeting: (meeting_type, {person}) for the other meeting held on the
    same date, if there is one.
    """
    names = dict(zip(students["id"], students["name"]))
    categories = dict(zip(students["id"], students["gender"]))
    families = dict(zip(students["id"], students["family"]))
    issues = []

    def add(level, where, text):
        issues.append({"level": level, "slots": sorted(where), "text": text})

    usage = {}
    for i, val in picks.items():
        if i >= 10000 or i >= len(slots):       # a visitor's name or congregation
            continue
        sid, aid = val
        part = slot_label(slots[i])
        if sid is not None and sid == aid:
            add("error", [i], f"{names.get(sid, '?')} is both student and "
                              f"assistant on '{part}'.")
        for pid in (sid, aid):
            if pid is not None:
                usage.setdefault(pid, []).append(i)
        if (sid is not None and aid is not None
                and categories.get(sid) != categories.get(aid)
                and not same_family(families, sid, aid)):
            add("warning", [i], f"'{part}': student and assistant are in "
                                "different categories and not family.")

    for pid, where in usage.items():
        where = sorted(set(where))
        if len(where) > 1:
            add("warning", where,
                f"{names.get(pid, '?')} has {len(where)} parts in this meeting: "
                + ", ".join(slot_label(slots[i]) for i in where) + ".")
        if pid in suspended:
            add("warning", where, f"{names.get(pid, '?')} is suspended but "
                                  "still assigned.")

    # the same part too close to this week, on either side
    gap = same_role_gap_days()
    for i, val in picks.items():
        if i >= 10000 or i >= len(slots) or val[0] is None:
            continue
        sid, role = val[0], slots[i]["role"]
        if role == "Watchtower Conductor":
            continue                   # one or two brothers take it every week
        before = last_role_dates(role, meeting_date).get(sid)
        after = next_role_dates(role, meeting_date).get(sid)
        if held_recently({sid: before} if before else {}, sid, meeting_date, gap):
            when = as_date(before)
            add("warning", [i], f"{names.get(sid, '?')} had '{role}' "
                                f"{relative_week(when, meeting_date)} "
                                f"({when.day} {when:%b}) — someone else would "
                                "usually take it this week.")
        if after and 0 < (as_date(after) - as_date(meeting_date)).days <= gap:
            when = as_date(after)
            add("warning", [i], f"{names.get(sid, '?')} already has '{role}' "
                                f"{relative_week(when, meeting_date)} "
                                f"({when.day} {when:%b}) as well.")

    if other_meeting:
        other_type, other_people = other_meeting
        for pid in set(usage) & set(other_people):
            add("warning", usage[pid], f"{names.get(pid, '?')} also has a part "
                                       f"in the {other_type} on this date.")
    return issues

