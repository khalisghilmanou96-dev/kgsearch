#!/usr/bin/env python3
"""Découverte et classement prudent des liens KSEARCHBOT."""

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from frontier import normalize_url

ROOT = Path(__file__).resolve().parent.parent

COUNTRIES = {
    item["code"]: item["tld"].lower()
    for item in json.loads(
        (ROOT / "search/countries.json").read_text(encoding="utf-8")
    )
}

TLD_COUNTRIES = {}
for code, tld in COUNTRIES.items():
    TLD_COUNTRIES.setdefault(tld, []).append(code)

EXCLUDED = re.compile(
    r"\.(pdf|jpg|jpeg|png|gif|svg|zip|mp4|mp3|webp|css|js|xml)$",
    re.I,
)


def infer_country(url):
    """Retourne un pays seulement si son TLD est non ambigu."""
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()

    if "." not in host:
        return None

    tld = host.rsplit(".", 1)[-1]
    matches = TLD_COUNTRIES.get(tld, [])

    if len(matches) == 1:
        return matches[0]

    return None



TRACKING_PARAMETERS = {
    "cookie_lang", "utm_source", "utm_medium", "utm_campaign",
    "utm_term", "utm_content", "fbclid", "gclid", "mc_cid", "mc_eid"
}


def clean_discovered_url(url):
    from urllib.parse import parse_qsl, urlencode, urlunsplit

    parsed = urlsplit(url)
    query = urlencode([
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMETERS
    ], doseq=True)

    return normalize_url(urlunsplit((
        parsed.scheme, parsed.netloc, parsed.path, query, ""
    )))


def discover_links(base_url, html, limit=500):
    """Extrait les URL HTTP(S) sans visiter les sites."""
    soup = BeautifulSoup(html, "html.parser")
    found = []
    seen = set()

    for tag in soup.find_all("a", href=True):
        target = clean_discovered_url(urljoin(base_url, tag["href"]))

        if not target:
            continue

        if EXCLUDED.search(urlsplit(target).path):
            continue

        if target in seen:
            continue

        seen.add(target)
        found.append({
            "url": target,
            "country_code": infer_country(target),
        })

        if len(found) >= limit:
            break

    return found


if __name__ == "__main__":
    sample = """
    <a href="https://example.fr/article">France</a>
    <a href="https://example.be/page">Belgique</a>
    <a href="https://example.com/news">International</a>
    """

    results = discover_links("https://example.com/", sample)

    assert len(results) == 3
    assert results[0]["country_code"] == "FR"
    assert results[1]["country_code"] == "BE"
    assert results[2]["country_code"] is None

    print("=== DÉCOUVERTE DES LIENS ===")
    for item in results:
        print(item["country_code"] or "INCONNU", item["url"])

    print("Tests : OK")
