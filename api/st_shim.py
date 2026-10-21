# -*- coding: utf-8 -*-
"""A stand-in for the few Streamlit features the shared Python modules use.

db.py, workbook.py and sheets_pdf.py were written for Streamlit and call
st.cache_data, st.cache_resource, st.secrets and st.session_state. Importing
this module first puts a small fake `streamlit` in sys.modules, so those
modules run unchanged inside the Vercel function (where Streamlit isn't
installed, or would cache data across requests if it were).

- cache_data memoises within one request only. Every request starts clean
  (see new_request), so a change made by the Next.js app or by the Streamlit
  app is always seen. The modules' own .clear() calls still work.
- cache_resource memoises for the life of the process (the connection pool,
  the registered fonts).
- secrets is empty: the database comes from MEETING_DSN.
- session_state holds the signed-in name, for the change log.
"""
import functools
import sys
import types

_data_caches = []


def _hashable(value):
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_hashable(v) for v in value)
    if isinstance(value, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in value.items()))
    return value


def _memo(func, registry):
    store = {}

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = (_hashable(args), _hashable(kwargs))
        if key not in store:
            store[key] = func(*args, **kwargs)
        return store[key]

    wrapper.clear = store.clear
    if registry is not None:
        registry.append(store)
    return wrapper


def _decorator(registry):
    def factory(func=None, **_options):
        if func is not None and callable(func):
            return _memo(func, registry)
        return lambda f: _memo(f, registry)
    return factory


def new_request(user_name=""):
    """Forget every per-request cache and record who is making the request."""
    for store in _data_caches:
        store.clear()
    session_state.clear()
    if user_name:
        session_state["user_name"] = user_name


session_state = {}

module = types.ModuleType("streamlit")
module.cache_data = _decorator(_data_caches)
module.cache_resource = _decorator(None)
module.secrets = {}
module.session_state = session_state
sys.modules["streamlit"] = module
