"""
Migrate the local financial_metrics.db to a Turso cloud database.

Usage:
    export TURSO_DATABASE_URL="libsql://your-db-name-your-org.turso.io"
    export TURSO_AUTH_TOKEN="your-token"
    python3 migrate_to_cloud.py

Copies every table (schema + rows) and recreates all views. Safe to
re-run: existing cloud tables are dropped and rebuilt from the local file.
"""

import os
import sqlite3
import sys

LOCAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financial_metrics.db")


def main():
    url = os.environ.get("TURSO_DATABASE_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN", "")

    if not url:
        print("TURSO_DATABASE_URL not set — nothing to do (app will use the local file).")
        sys.exit(0)

    if not os.path.exists(LOCAL_DB):
        print(f"Local database not found: {LOCAL_DB}")
        sys.exit(1)

    import libsql

    print(f"Connecting to cloud database: {url.split('@')[-1]}")
    remote = libsql.connect(url, auth_token=token)

    local = sqlite3.connect(f"file:{LOCAL_DB}?mode=ro", uri=True)
    lcur = local.cursor()

    # ---- Tables ----
    lcur.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    tables = lcur.fetchall()

    # Drop views first (they may depend on tables), then tables
    rcur = remote.cursor()
    rcur.execute("SELECT name FROM sqlite_master WHERE type='view'")
    for (vname,) in rcur.fetchall():
        remote.execute(f'DROP VIEW IF EXISTS "{vname}"')
    for name, _ in tables:
        remote.execute(f'DROP TABLE IF EXISTS "{name}"')
    remote.commit()

    # Create all tables first (metric tables have foreign keys to filings,
    # which libsql enforces at insert time)
    for _, create_sql in tables:
        remote.execute(create_sql)
    remote.commit()

    # Insert parent tables before children to satisfy foreign keys
    priority = {'companies': 0, 'filings': 1}
    ordered_names = sorted([n for n, _ in tables], key=lambda n: (priority.get(n, 2), n))

    total_rows = 0
    for name in ordered_names:
        lcur.execute(f'SELECT * FROM "{name}"')
        rows = lcur.fetchall()
        if rows:
            placeholders = ", ".join(["?"] * len(rows[0]))
            for row in rows:
                remote.execute(f'INSERT INTO "{name}" VALUES ({placeholders})', row)
        remote.commit()

        total_rows += len(rows)
        print(f"  {name}: {len(rows)} rows")

    # ---- Views ----
    lcur.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='view' ORDER BY name"
    )
    views = lcur.fetchall()
    for name, create_sql in views:
        remote.execute(create_sql)
    remote.commit()
    print(f"  {len(views)} views recreated")

    # ---- Verify ----
    rcur = remote.cursor()
    rcur.execute("SELECT COUNT(*) FROM companies")
    companies = rcur.fetchone()[0]
    rcur.execute("SELECT COUNT(*) FROM all_metrics")
    metrics = rcur.fetchone()[0]

    local.close()

    print(f"\nMigration complete: {total_rows} rows copied")
    print(f"Cloud verification: {companies} companies, {metrics} metrics")


if __name__ == "__main__":
    main()
