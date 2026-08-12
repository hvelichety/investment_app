"""
Database backend selector.

If TURSO_DATABASE_URL is set, connections prefer a Turso cloud database
(SQLite-compatible, via libsql). If the cloud database is unreachable or
missing required tables, the bundled local financial_metrics.db is used
instead so the app keeps serving data.

Both paths return sqlite3-style DB-API connections, so the rest of the
codebase works unchanged.
"""

import os
import sqlite3
import threading

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(ROOT_DIR, "data", "financial_metrics.db")

REQUIRED_TABLES = (
    "companies",
    "filings",
    "revenue_metrics",
    "profitability_metrics",
    "margin_metrics",
    "balance_sheet_metrics",
    "cash_flow_metrics",
    "per_share_metrics",
    "operational_metrics",
    "valuation_metrics",
    "all_metrics",
)

_lock = threading.Lock()
_resolved = None  # cached: {"mode": "turso"|"local", "reason": str|None}


def is_cloud_configured() -> bool:
    return bool(os.environ.get("TURSO_DATABASE_URL"))


def _list_tables(conn) -> set:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return {row[0] for row in cursor.fetchall()}


def _missing_required_tables(conn) -> list:
    present = _list_tables(conn)
    return [name for name in REQUIRED_TABLES if name not in present]


def _connect_turso():
    import libsql
    url = os.environ.get("TURSO_DATABASE_URL")
    return libsql.connect(url, auth_token=os.environ.get("TURSO_AUTH_TOKEN", ""))


def _connect_local(readonly: bool = False, db_path: str = None):
    path = db_path or DEFAULT_DB_PATH
    if readonly:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    # check_same_thread=False allows use from Flask request threads;
    # access is serialized with a lock in the web layer.
    return sqlite3.connect(path, check_same_thread=False)


def resolve_backend(force: bool = False) -> dict:
    """Decide whether to use Turso or the local file. Result is cached."""
    global _resolved
    with _lock:
        if _resolved is not None and not force:
            return _resolved

        if not is_cloud_configured():
            _resolved = {"mode": "local", "reason": None}
            return _resolved

        try:
            conn = _connect_turso()
            try:
                missing = _missing_required_tables(conn)
            finally:
                conn.close()
        except Exception as exc:
            _resolved = {
                "mode": "local",
                "reason": f"turso connection failed: {exc}",
            }
            return _resolved

        if missing:
            _resolved = {
                "mode": "local",
                "reason": (
                    "turso schema incomplete (missing: "
                    + ", ".join(missing)
                    + "); run scripts/migrate_to_cloud.py"
                ),
            }
            return _resolved

        _resolved = {"mode": "turso", "reason": None}
        return _resolved


def get_connection(readonly: bool = False, db_path: str = None):
    """Return a DB-API connection to the cloud database or the local file."""
    # Explicit local path always wins (tests / offline tools).
    if db_path:
        return _connect_local(readonly=readonly, db_path=db_path)

    backend = resolve_backend()
    if backend["mode"] == "turso":
        return _connect_turso()
    return _connect_local(readonly=readonly, db_path=db_path)


def backend_name() -> str:
    backend = resolve_backend()
    if backend["mode"] == "turso":
        return "turso"
    if is_cloud_configured() and backend.get("reason"):
        return "sqlite (local fallback)"
    return "sqlite (local file)"


def backend_status() -> dict:
    """Structured backend info for /status and diagnostics."""
    backend = resolve_backend()
    return {
        "backend": backend_name(),
        "mode": backend["mode"],
        "cloud_configured": is_cloud_configured(),
        "fallback_reason": backend.get("reason"),
    }
