#!/usr/bin/env python3
"""File d'attente persistante des URL KSEARCHBOT."""

import argparse
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "crawler" / "data" / "frontier.sqlite"


def normalize_url(url):
    try:
        parsed = urlsplit(url.strip())
        host = (parsed.hostname or "").lower().rstrip(".")

        if (
            parsed.scheme not in ("http", "https")
            or not host
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 80, 443)
        ):
            return None

        return urlunsplit((
            parsed.scheme,
            host,
            parsed.path or "/",
            parsed.query,
            ""
        ))
    except (ValueError, AttributeError):
        return None


def connect(path=DEFAULT_DB):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(path, timeout=30)

    con.execute("""
        CREATE TABLE IF NOT EXISTS frontier (
            url TEXT PRIMARY KEY,
            country_code TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            discovered_at INTEGER NOT NULL,
            last_crawled_at INTEGER,
            next_crawl_at INTEGER NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
        )
    """)

    con.execute("""
        CREATE INDEX IF NOT EXISTS frontier_schedule
        ON frontier(status, next_crawl_at)
    """)

    con.commit()
    return con


def add_url(con, url, country_code=None):
    url = normalize_url(url)

    if not url:
        return False

    now = int(time.time())

    cursor = con.execute("""
        INSERT OR IGNORE INTO frontier (
            url, country_code, status,
            discovered_at, next_crawl_at
        )
        VALUES (?, ?, 'pending', ?, ?)
    """, (url, country_code, now, now))

    con.commit()
    return cursor.rowcount > 0


def stats(con):
    rows = con.execute("""
        SELECT status, COUNT(*)
        FROM frontier
        GROUP BY status
    """).fetchall()

    return dict(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--add")
    parser.add_argument("--country")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    con = connect(args.db)

    if args.add:
        added = add_url(con, args.add, args.country)
        print("URL ajoutée :", added)

    if args.stats or not args.add:
        print("=== KSEARCHBOT FRONTIER ===")
        print("Base :", args.db)
        print("Statistiques :", stats(con))
        print("Intégrité :", con.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0])

    con.close()


if __name__ == "__main__":
    main()
