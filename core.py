# -*- coding: utf-8 -*-
"""Everything the pages need, in one import: `from core import *`."""
import json  # noqa: F401

from s140 import S140Error, fill_s140  # noqa: F401

from picking import *  # noqa: F401,F403
from i18n import *  # noqa: F401,F403


def go(page, **state):
    """Switch page, optionally presetting widget state, and rerun."""
    st.session_state["menu"] = page
    for key, value in state.items():
        st.session_state[key] = value
    st.rerun()
