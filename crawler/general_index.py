#!/usr/bin/env python3
"""Indexation HTML généraliste compatible avec KSEARCHBOT."""

import sqlite3
import time
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from link_discovery import infer_country


def extract_page(url, html):
    soup = BeautifulSoup(html, "html.parser")

    robots = soup.find(
        "meta",
        attrs={"name": lambda x: isinstance(x, str) and x.lower() == "robots"}
    )

    if robots and "noindex" in robots.get("content", "").lower():
        return None

    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    description_tag = soup.find(
        "meta",
        attrs={"name": lambda x: isinstance(x, str) and x.lower() == "description"}
    )

    description = (
        description_tag.get("content", "").strip()
        if description_tag else ""
    )

    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    content = " ".join(soup.get_text(" ", strip=True).split())[:30000]

    if not content:
        return None

    if not description:
        description = content[:250]

    return {
        "url": url,
        "host": urlsplit(url).hostname or "",
        "tld": (urlsplit(url).hostname or "").rsplit(".", 1)[-1],
        "country_code": infer_country(url),
        "title": title[:250],
        "description": description[:500],
        "content": content,
        "crawled_at": int(time.time()),
    }


def index_page(con, page):
    con.execute("""
        CREATE TABLE IF NOT EXISTS pages (
            url TEXT PRIMARY KEY,
            host TEXT NOT NULL,
            tld TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            content TEXT NOT NULL,
            crawled_at INTEGER NOT NULL
        )
    """)

    con.execute("""
        INSERT INTO pages (
            url, host, tld, title, description, content, crawled_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title=excluded.title,
            description=excluded.description,
            content=excluded.content,
            crawled_at=excluded.crawled_at
    """, (
        page["url"],
        page["host"],
        page["tld"],
        page["title"],
        page["description"],
        page["content"],
        page["crawled_at"],
    ))

    con.commit()


if __name__ == "__main__":
    import tempfile

    html = """
    <html>
    <head>
      <title>Exemple international</title>
      <meta name="description" content="Page de test KSEARCHBOT">
    </head>
    <body>
      <h1>Bienvenue</h1>
      <p>Contenu généraliste international.</p>
    </body>
    </html>
    """

    with tempfile.TemporaryDirectory() as folder:
        con = sqlite3.connect(Path(folder) / "index-test.sqlite")

        page = extract_page("https://example.com/article", html)

        assert page is not None
        assert page["country_code"] is None

        index_page(con, page)
        index_page(con, page)

        count = con.execute(
            "SELECT COUNT(*) FROM pages"
        ).fetchone()[0]

        integrity = con.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        assert count == 1
        assert integrity == "ok"

        print("=== INDEXATION GÉNÉRALISTE ===")
        print("Titre :", page["title"])
        print("Pays :", page["country_code"] or "INCONNU")
        print("Pages enregistrées :", count)
        print("Intégrité :", integrity)
        print("Tests : OK")

        con.close()
