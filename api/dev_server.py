# -*- coding: utf-8 -*-
"""Serves api/py.py on http://127.0.0.1:8001 for local development (`npm run dev:py`).

On Vercel the same file runs as a function; `next dev` forwards /api/py here.
Reads DATABASE_URL and SESSION_SECRET from .env when they aren't already set.
"""
import os
from http.server import HTTPServer
from pathlib import Path

env = Path(__file__).resolve().parent.parent / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').replace("\\$", "$"))

from py import handler  # noqa: E402


if __name__ == "__main__":
    print("Python function on http://127.0.0.1:8001/api/py")
    HTTPServer(("127.0.0.1", 8001), handler).serve_forever()
