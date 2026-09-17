# -*- coding: utf-8 -*-
"""Password gate.

Secrets (Streamlit Cloud → Settings → Secrets, or .streamlit/secrets.toml):

    [auth]
    password = "shared-password"      # everyone uses this and types their name

    # …or give each person their own password instead:
    [auth.users]
    Xan = "first-password"
    Kofi = "second-password"
"""
import hmac

from sheets import *  # noqa: F401,F403


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
    return {"password": password, "users": users}


def login_enabled():
    return _auth_config() is not None


def _matches(given, expected):
    return bool(expected) and hmac.compare_digest(str(given), str(expected))


def require_login():
    """Stop the page until the right password is given. Returns True when open."""
    cfg = _auth_config()
    if cfg is None:
        return True
    if st.session_state.get("auth_ok"):
        return True

    st.title("📅 Meeting Scheduler")
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
            log_change("Signed in", name)
            st.rerun()
        else:
            st.error("Wrong name or password.")
    st.stop()


def logout_button():
    if not login_enabled():
        return
    who = st.session_state.get("user_name", "")
    if st.sidebar.button(f"🔒 Sign out {who}".strip(), width="stretch"):
        for key in ("auth_ok", "user_name"):
            st.session_state.pop(key, None)
        st.rerun()
