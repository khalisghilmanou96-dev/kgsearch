import os
import sqlite3
from pathlib import Path
#!/usr/bin/env python3
"""Exploration prudente des URL mémorisées par KSEARCHBOT."""

import argparse
import ipaddress
import logging
import socket
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
from safe_http import create_session

from frontier import connect
from frontier_discovery import save_discovered_links
from general_index import extract_page, index_page
from network_safety import validate_url
from link_discovery import infer_country

AGENT = "KSEARCHBOT/1.0 (+https://kgstudio.fr/search/; contact: contact@kgstudio.fr)"
LOG = logging.getLogger("frontier_runner")


def public_host(host):
    if not host or host == "localhost" or host.endswith(".local"):
        return False

    try:
        addresses = socket.getaddrinfo(
            host, None, type=socket.SOCK_STREAM
        )
        return bool(addresses) and all(
            ipaddress.ip_address(item[4][0]).is_global
            for item in addresses
        )
    except (OSError, ValueError):
        return False


def robots_allowed(session, url):
    parsed = urlsplit(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        response = session.get(
            robots_url,
            timeout=10,
            allow_redirects=False
        )

        if response.status_code == 200:
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            return parser.can_fetch(AGENT, url)

        if response.status_code in (404, 410):
            return True

        return False

    except requests.RequestException:
        return False


def run(limit, delay, dry_run=False):
    frontier_path = os.environ.get("KSEARCH_FRONTIER_DB")
    con = connect(Path(frontier_path)) if frontier_path else connect()
    session = create_session()
    session.trust_env = False
    session.headers.update({"User-Agent": AGENT})

    now = int(time.time())

    rows = con.execute("""
        SELECT url, country_code
        FROM frontier
        WHERE status IN ('pending', 'done')
          AND next_crawl_at <= ?
        ORDER BY discovered_at
        LIMIT ?
    """, (now, limit)).fetchall()

    if dry_run:
        print("=== KSEARCHBOT : SIMULATION ===")
        print("URL sélectionnées :", len(rows))
        for url, country in rows:
            print(country or "INCONNU", url)
        con.close()
        return

    processed = 0
    succeeded = 0

    for url, country in rows:
        processed += 1
        host = urlsplit(url).hostname

        try:
            if not public_host(host):
                raise ValueError("Hôte non public ou inaccessible")

            if not robots_allowed(session, url):
                raise ValueError("Accès refusé par robots.txt")

            time.sleep(delay)

            response = session.get(
                url,
                timeout=12,
                allow_redirects=False,
                stream=True
            )

            try:
                if response.status_code != 200:
                    raise ValueError(
                        f"HTTP {response.status_code}"
                    )

                if "text/html" not in response.headers.get(
                    "Content-Type", ""
                ).lower():
                    raise ValueError("Contenu non HTML")

                raw = response.raw.read(
                    2_000_001,
                    decode_content=True
                )

                if len(raw) > 2_000_000:
                    raise ValueError("Page trop volumineuse")

                html = raw.decode(
                    response.encoding or "utf-8",
                    errors="replace"
                )
            finally:
                response.close()

            from link_discovery import discover_links
            from frontier import add_url

            candidates = discover_links(url, html, limit=100)
            added = 0

            for candidate in candidates:
                if added >= 20:
                    break

                candidate_url = candidate["url"]

                try:
                    validate_url(candidate_url)
                except (ValueError, OSError):
                    continue

                if add_url(
                    con,
                    candidate_url,
                    candidate["country_code"]
                ):
                    added += 1

            result = {"added": added}

            page = extract_page(url, html)
            if page is not None:
                index_path = Path(
                    os.environ.get(
                        "KSEARCH_INDEX_DB",
                        str(
                            Path(__file__).resolve().parents[1]
                            / "search" / "data" / "index.sqlite"
                        )
                    )
                )
                index_path.parent.mkdir(parents=True, exist_ok=True)
                with sqlite3.connect(index_path) as index_con:
                    index_page(index_con, page)
                result["indexed"] = True
            else:
                result["indexed"] = False

            con.execute("""
                UPDATE frontier
                SET status = 'done',
                    country_code = COALESCE(country_code, ?),
                    last_crawled_at = ?,
                    next_crawl_at = ?,
                    attempts = attempts + 1,
                    last_error = NULL
                WHERE url = ?
            """, (
                infer_country(url),
                now,
                now + 86400,
                url
            ))

            succeeded += 1

            LOG.info(
                "OK %s : %d nouveaux liens",
                url,
                result["added"]
            )

        except (requests.RequestException, ValueError, OSError, sqlite3.Error) as exc:
            con.execute("""
                UPDATE frontier
                SET status = 'pending',
                    attempts = attempts + 1,
                    next_crawl_at = ?,
                    last_error = ?
                WHERE url = ?
            """, (
                int(time.time()) + 86400,
                str(exc)[:500],
                url
            ))

            LOG.warning("Échec %s : %s", url, exc)

        con.commit()

    con.close()

    print("=== KSEARCHBOT FRONTIER RUNNER ===")
    print("URL traitées :", processed)
    print("URL réussies :", succeeded)
    print("URL en échec :", processed - succeeded)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not 1 <= args.limit <= 100:
        parser.error("limit doit être entre 1 et 100")

    if args.delay < 1:
        parser.error("delay doit être >= 1")

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s"
    )

    run(args.limit, args.delay, args.dry_run)


if __name__ == "__main__":
    main()
