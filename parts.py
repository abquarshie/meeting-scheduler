# -*- coding: utf-8 -*-
"""Default part lists for each meeting."""
from db import *  # noqa: F401,F403


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
        make_slot("Watchtower Conductor", "Watchtower Conductor", "Weekend"),
        make_slot("Watchtower Reader", "Watchtower Reader", "Weekend"),
        make_slot("Closing Prayer", "Prayer", "Weekend"),
    ]
