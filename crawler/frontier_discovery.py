#!/usr/bin/env python3
"""Enregistre les liens découverts dans la mémoire KSEARCHBOT."""

import argparse
from pathlib import Path

from frontier import connect, add_url, stats
from link_discovery import discover_links


def save_discovered_links(base_url, html, db_path=None):
    links = discover_links(base_url, html)

    if db_path is None:
        con = connect()
    else:
        con = connect(db_path)

    added = 0

    try:
        for item in links:
            if add_url(
                con,
                item["url"],
                item["country_code"]
            ):
                added += 1

        return {
            "discovered": len(links),
            "added": added,
            "duplicates": len(links) - added,
        }
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    if args.test:
        import tempfile

        html = """
        <a href="https://example.fr/article">France</a>
        <a href="https://example.be/page">Belgique</a>
        <a href="https://example.com/news">International</a>
        <a href="https://example.fr/article">Doublon</a>
        """

        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "test.sqlite"

            first = save_discovered_links(
                "https://example.com/",
                html,
                db_path
            )

            second = save_discovered_links(
                "https://example.com/",
                html,
                db_path
            )

            con = connect(db_path)
            count = con.execute(
                "SELECT COUNT(*) FROM frontier"
            ).fetchone()[0]

            integrity = con.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

            con.close()

            assert first["added"] == 3
            assert second["added"] == 0
            assert count == 3
            assert integrity == "ok"

            print("=== KSEARCHBOT : TEST DÉCOUVERTE ===")
            print("Première découverte :", first)
            print("Deuxième découverte :", second)
            print("URL enregistrées :", count)
            print("Intégrité :", integrity)
            print("Tests : OK")


if __name__ == "__main__":
    main()
