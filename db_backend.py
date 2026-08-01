"""
Database backend selector.

If TURSO_DATABASE_URL is set, connections go to a Turso cloud database
(SQLite-compatible, via libsql). Otherwise, the local financial_metrics.db
file is used. Both return sqlite3-style DB-API connections, so the rest
of the codebase works unchanged.
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "financial_metrics.db")


def is_cloud_configured() -> bool:
    return bool(os.environ.get("TURSO_DATABASE_URL"))


def get_connection(readonly: bool = False, db_path: str = None):
    """Return a DB-API connection to the cloud database or the local file."""
    url = os.environ.get("TURSO_DATABASE_URL")
    if url:
        import libsql
        return libsql.connect(url, auth_token=os.environ.get("TURSO_AUTH_TOKEN", ""))

    path = db_path or DEFAULT_DB_PATH
    if readonly:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    # check_same_thread=False allows use from Flask request threads;
    # access is serialized with a lock in app.py.
    return sqlite3.connect(path, check_same_thread=False)


def backend_name() -> str:
    return "turso" if is_cloud_configured() else "sqlite (local file)"
