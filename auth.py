# -*- coding: utf-8 -*-
"""Password gate and role assignment for Life and Ministry Overseer & Talk Coordinator.

Secrets (Streamlit Cloud → Settings → Secrets, or .streamlit/secrets.toml):

    [auth.users]
    "Overseer Name" = "password-midweek"
    "Coordinator Name" = "password-weekend"
"""
import hmac
from backup import *  # noqa: F401,F403

ROLE_OVERSEER = "Life and Ministry Overseer"
ROLE_COORDINATOR = "Talk Coordinator"
ROLE_ADMIN = "Admin"  # Optional or fallback if configured

def _auth_config():
    try:
        auth = st.secrets.get("auth")
    except Exception:
        return None
    if not auth:
        return None
    users = dict(auth.get("users", {}) or {})
    roles = dict(auth.get("roles", {}) or {})
    password = auth.get("password")
    if not users and not password:
        return None
    return {"password": password, "users": users, "roles": roles}

def login_enabled():
    return _auth_config() is not None

def _matches(given, expected):
    return bool(expected) and hmac.compare_digest(str(given), str(expected))

def get_user_role(name):
    cfg = _auth_config()
    if not cfg:
        return ROLE_OVERSEER # Default fallback if auth is disabled
    roles = cfg.get("roles", {})
    if name in roles:
        return roles[name]
    # Heuristic fallback based on name or default to Overseer if not specified
    name_lower = name.lower()
    if "coord" in name_lower or "talk" in name_lower:
        return ROLE_COORDINATOR
    return ROLE_OVERSEER

def require_login():
    """Stop the page until the right password is given and assign user role."""
    cfg = _auth_config()
    if cfg is None:
        st.session_state["user_role"] = ROLE_OVERSEER
        return True
    if st.session_state.get("auth_ok"):
        return True

    from ui import inject_css, page_header
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
            st.session_state["user_role"] = get_user_role(name)
            log_change("Signed in", f"{name} ({st.session_state['user_role']})")
            st.rerun()
        else:
            st.error("Wrong name or password.")
    st.stop()

def logout_button():
    if not login_enabled():
        return
    who = st.session_state.get("user_name", "")
    role = st.session_state.get("user_role", "")
    if st.sidebar.button(f"Sign out {who}".strip(), icon=":material/logout:",
                         type="tertiary", width="stretch"):
        for key in ("auth_ok", "user_name", "user_role"):
            st.session_state.pop(key, None)
        st.rerun()

def current_user_role():
    return st.session_state.get("user_role", ROLE_OVERSEER)

def can_manage_midweek():
    role = current_user_role()
    return role in (ROLE_OVERSEER, ROLE_ADMIN)

def can_manage_weekend():
    role = current_user_role()
    return role in (ROLE_COORDINATOR, ROLE_ADMIN)
