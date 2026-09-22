# File: auth.py
# -*- coding: utf-8 -*-
"""Password gate and per-user roles.

Secrets (Streamlit Cloud → Settings → Secrets, or .streamlit/secrets.toml):

    [auth]
    password = "shared-password"      # everyone uses this and types their name

    # …or give each person their own password instead:
    [auth.users]
    Xan = "first-password"
    Kofi = "second-password"

    # …and say what each person may do. Anyone unlisted gets full access.
    [auth.roles]
    Xan = "overseer"        # Life and Ministry Overseer (midweek)
    Kofi = "coordinator"    # Talk Coordinator (weekend)
"""
import hmac

from backup import *  # noqa: F401,F403

# The two roles and the meeting types each may touch. An empty set means
# "everything" — that is what an unlisted user gets.
OVERSEER = "overseer"
COORDINATOR = "coordinator"
ROLE_MEETINGS = {
    OVERSEER: {MIDWEEK},
    COORDINATOR: {WEEKEND},
    "": set(),               # full access
    None: set(),
}
ROLE_LABELS = {
    OVERSEER: "Life and Ministry Overseer",
    COORDINATOR: "Talk Coordinator",
    "": "Full access",
    None: "Full access",
}


def _auth_config():
    try:
        auth = st.secrets.get("auth")
    except Exception:
        return None
    if not auth:
        return None
    users = dict(auth.get("users", {}) or {})
    password = auth.get("password")
    if not users and not password:
        return None
    return {
        "password": password,
        "users": users,
        "roles": dict(auth.get("roles", {}) or {}),
    }


def login_enabled():
    return _auth_config() is not None


def _matches(given, expected):
    return bool(expected) and hmac.compare_digest(str(given), str(expected))


# --- roles ------------------------------------------------------------------

def current_role():
    """The signed-in user's role, or "" for full access."""
    return st.session_state.get("user_role", "")


def role_label(role=None):
    """Human-readable name for a role."""
    return ROLE_LABELS.get(current_role() if role is None else role, "Full access")


def allowed_meetings(role=None):
    """Meeting types this role may touch. Empty set = all."""
    role = current_role() if role is None else role
    return ROLE_MEETINGS.get(role, set())


def may_touch(meeting_type, role=None):
    """True when the role is allowed to see or edit this meeting type."""
    allowed = allowed_meetings(role)
    return not allowed or meeting_type in allowed


def filter_schedules(df, role=None):
    """Trim a schedules DataFrame to the meetings this role may see.

    Both roles read the same tables; only the rows each is responsible for
    reach the page. Passing a role with no restriction returns df unchanged.
    """
    allowed = allowed_meetings(role)
    if not allowed or df is None or df.empty:
        return df
    return df[df["meeting_type"].isin(allowed)]


# --- sign-in ----------------------------------------------------------------

def require_login():
    """Stop the page until the right password is given. Returns True when open."""
    cfg = _auth_config()
    if cfg is None:
        return True
    if st.session_state.get("auth_ok"):
        return True

    from ui import inject_css, page_header  # imported here: ui builds on this module
    from i18n import tr
    inject_css()
    page_header(tr("app_name"), "Sign in to manage assignments.")
    with st.form("login"):
        name = st.text_input("Your name")
        password = st.text_input("Password", type="password")
        ok = st.form_submit_button("Sign in", type="primary")
    if ok:
        name = nfc(name)
        user_pw = cfg["users"].get(name)
        if not name:
            st.error("Enter your name so changes can be credited to you.")
        elif _matches(password, user_pw) or (
                not cfg["users"] and _matches(password, cfg["password"])) or (
                user_pw is None and _matches(password, cfg["password"])):
            st.session_state["auth_ok"] = True
            st.session_state["user_name"] = name
            st.session_state["user_role"] = cfg["roles"].get(name, "")
            log_change("Signed in",
                       f"{name} ({ROLE_LABELS.get(st.session_state['user_role'], 'Full access')})")
            st.rerun()
        else:
            st.error("Wrong name or password.")
    st.stop()


def logout_button():
    if not login_enabled():
        return
    who = st.session_state.get("user_name", "")
    if st.sidebar.button(f"Sign out {who}".strip(), icon=":material/logout:",
                         type="tertiary", width="stretch"):
        for key in ("auth_ok", "user_name", "user_role"):
            st.session_state.pop(key, None)
        st.rerun()
