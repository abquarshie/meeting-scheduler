# -*- coding: utf-8 -*-
"""Password gate, with each account scoped to a role.

Secrets (Streamlit Cloud → Settings → Secrets, or .streamlit/secrets.toml):

    [auth]
    password = "shared-password"      # everyone uses this and types their name
                                       # (full access to both meetings)

    # …or give each person their own account, with a role that decides which
    # meeting they may create and edit (everything else stays shared, and both
    # accounts see the same participants, workbook, settings and so on):
    [auth.users.Kofi]
    password = "first-password"
    role = "overseer"                 # Life and Ministry Overseer: midweek

    [auth.users.Ama]
    password = "second-password"
    role = "talks"                    # Talk Coordinator: weekend

    # A role of "both" (or an account with no role at all) has full access to
    # both meetings — useful for an elder overseeing everything, or while
    # moving off the old shared-password setup a name at a time.
"""
import hmac

from backup import *  # noqa: F401,F403


def _auth_config():
    try:
        auth = st.secrets.get("auth")
    except Exception:
        return None
    if not auth:
        return None
    raw_users = dict(auth.get("users", {}) or {})
    users = {}
    for name, value in raw_users.items():
        if isinstance(value, str):
            # the old shape — name = "password" — kept working, full access
            users[name] = {"password": value, "role": ROLE_BOTH}
            continue
        role = str(value.get("role", "") or "").strip().lower()
        if role not in USER_ROLES:
            role = ROLE_BOTH
        users[name] = {"password": value.get("password"), "role": role}
    password = auth.get("password")
    if not users and not password:
        return None
    return {"password": password, "users": users}


def login_enabled():
    return _auth_config() is not None


def _matches(given, expected):
    return bool(expected) and hmac.compare_digest(str(given), str(expected))


def current_role():
    """The signed-in user's role. Full access when sign-in isn't configured at
    all, or for an account with no role of its own."""
    try:
        return st.session_state.get("user_role", ROLE_BOTH)
    except Exception:
        return ROLE_BOTH


def user_role_label(role=None):
    return USER_ROLE_LABELS.get(role if role is not None else current_role(), "")


def managed_meeting_type():
    """The one meeting type the signed-in user may create and edit, or None
    if they have full access to both (the usual case when sign-in isn't
    configured, or for a "both" account)."""
    return USER_ROLE_MEETING_TYPE.get(current_role())


def can_manage(meeting_type):
    """True if the signed-in user may create or edit this meeting type."""
    role = current_role()
    if role == ROLE_BOTH:
        return True
    return USER_ROLE_MEETING_TYPE.get(role) == meeting_type


def require_login():
    """Stop the page until the right password is given. Returns True when open."""
    cfg = _auth_config()
    if cfg is None:
        st.session_state.setdefault("user_role", ROLE_BOTH)
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
        entry = cfg["users"].get(name)
        user_pw = entry.get("password") if entry else None
        if not name:
            st.error("Enter your name so changes can be credited to you.")
        elif _matches(password, user_pw) or (
                not cfg["users"] and _matches(password, cfg["password"])) or (
                user_pw is None and _matches(password, cfg["password"])):
            st.session_state["auth_ok"] = True
            st.session_state["user_name"] = name
            st.session_state["user_role"] = entry["role"] if entry else ROLE_BOTH
            log_change("Signed in", name)
            st.rerun()
        else:
            st.error("Wrong name or password.")
    st.stop()


def logout_button():
    if not login_enabled():
        return
    who = st.session_state.get("user_name", "")
    role = current_role()
    if role != ROLE_BOTH:
        st.sidebar.caption(f":material/badge: {user_role_label(role)}")
    if st.sidebar.button(f"Sign out {who}".strip(), icon=":material/logout:",
                         type="tertiary", width="stretch"):
        for key in ("auth_ok", "user_name", "user_role"):
            st.session_state.pop(key, None)
        st.rerun()
