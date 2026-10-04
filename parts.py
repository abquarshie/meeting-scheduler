# -*- coding: utf-8 -*-
"""Default part lists for each meeting."""
from utils import make_slot


# =============================================================================
# DEFAULT PART LISTS
# =============================================================================
def default_midweek_parts():
    """The numbered parts only (what a brochure would supply)."""
    return [
        make_slot("Treasures Talk", "Treasures Talk", "Treasures", 1, 10),
        make_slot("Spiritual Gems", "Spiritual Gems", "Treasures", 2, 10),
        make_slot("Bible Reading", "Bible Reading", "Treasures", 3, 4),
        make_slot("Initial Presentation", "Initial Presentation", "Ministry", 4, 3),
        make_slot("Making Disciples", "Making Disciples", "Ministry", 5, 4),
        make_slot("Explaining Your Beliefs", "Explaining Beliefs", "Ministry", 6, 5),
        make_slot("Living Part", "Living Part", "Living", 7, 15),
        make_slot("Congregation Bible Study", "Bible Study Conductor", "Living", 8, 30),
    ]


def build_midweek_slots(parts):
    """Wrap the numbered parts with the fixed roles every week needs."""
    slots = [
        make_slot("Chairman", "Chairman", "Opening"),
        make_slot("Opening Prayer", "Prayer", "Opening"),
    ]
    reader_added = False
    for part in parts:
        slots.append(dict(part))
        if part["role"] == "Bible Study Conductor":
            slots.append(make_slot("Congregation Bible Study Reader", "Reader", "Living"))
            reader_added = True
    if not reader_added:
        slots.append(make_slot("Congregation Bible Study Reader", "Reader", "Living"))
    slots.append(make_slot("Closing Prayer", "Prayer", "Closing"))
    return slots


def default_weekend_slots():
    return [
        make_slot("Chairman", "Weekend Chairman", "Weekend"),
        make_slot("Opening Prayer", "Prayer", "Weekend"),
        {**make_slot("Public Talk Speaker", "Public Talk", "Weekend"), "allow_visitor": True},
        make_slot("Watchtower Reader", "Watchtower Reader", "Weekend"),
        make_slot("Closing Prayer", "Prayer", "Weekend"),
    ]


# A symposium: one public talk shared by two speakers, both brothers from the
# congregation (guest speakers don't give them). The second speaker is a slot
# of his own, so each is chosen, rotated and reminded like any speaker.
FIRST_SPEAKER = "Public Talk Speaker"
SECOND_SPEAKER = "Public Talk Speaker 2"


def is_symposium(slots):
    return any(s["title"] == SECOND_SPEAKER for s in slots)


def apply_symposium(slots, on):
    """Add (or remove) the second speaker, right after the first."""
    out = [s for s in slots if s["title"] != SECOND_SPEAKER]
    if not on:
        return out
    for i, s in enumerate(out):
        if s["role"] == "Public Talk":
            second = {**make_slot(SECOND_SPEAKER, "Public Talk", s["section"]),
                      "allow_visitor": False}
            return out[:i + 1] + [second] + out[i + 1:]
    return out

