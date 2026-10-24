#!/usr/bin/env python3
import argparse
import ipaddress
import json
import socket
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
AGENT = "KSEARCHBOT/1.0 (+https://kgstudio.fr/search/)"
TIMEOUT = 8

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

opener = urllib.request.build_opener(NoRedirect)

def public_host(host):
    try:
        addresses = socket.getaddrinfo(
            host, 443, type=socket.SOCK_STREAM
        )
        return bool(addresses) and all(
            ipaddress.ip_address(item[4][0]).is_global
            for item in addresses
        )
    except (OSError, ValueError):
        return False

def verify(url, tld):
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""

        if (
            parsed.scheme != "https"
            or host != "www.gov." + tld
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
            or not public_host(host)
        ):
            return False

        robots_url = "https://" + host + "/robots.txt"
        req = urllib.request.Request(
            robots_url,
            headers={"User-Agent": AGENT}
        )

        try:
            with opener.open(req, timeout=TIMEOUT) as response:
                status = response.status
                raw = response.read(500001)
                if len(raw) > 500000:
                    return False
                rules = raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            status = error.code
            rules = ""
        except Exception:
            return False

        if status in (401, 403) or status >= 500:
            return False

        if status not in (200, 404, 410):
            return False

        robots = urllib.robotparser.RobotFileParser()
        robots.parse(
            rules.splitlines() if status == 200 else []
        )

        if not robots.can_fetch(AGENT, url):
            return False

        req = urllib.request.Request(
            url,
            headers={"User-Agent": AGENT}
        )

        with opener.open(req, timeout=TIMEOUT) as response:
            content_type = response.headers.get(
                "Content-Type", ""
            ).lower()

            return (
                response.status == 200
                and "text/html" in content_type
            )

    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="crawler/runtime_seeds.json"
    )
    args = parser.parse_args()

    countries = json.loads(
        (ROOT / "search/countries.json").read_text(
            encoding="utf-8"
        )
    )

    existing = json.loads(
        (ROOT / "crawler/seeds.json").read_text(
            encoding="utf-8"
        )
    )

    result = {}
    discovered = 0

    for country in countries:
        code = country["code"]
        tld = country["tld"].lower().lstrip(".")

        urls = [
            u for u in existing.get(code, [])
            if isinstance(u, str)
            and u.startswith("https://")
        ]

        candidate = f"https://www.gov.{tld}/"

        if candidate not in urls and verify(candidate, tld):
            urls.append(candidate)
            discovered += 1

        result[code] = urls

    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    output.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    active = sum(bool(v) for v in result.values())

    print("=== KSEARCHBOT AUTO DISCOVERY ===")
    print("Pays examinés :", len(countries))
    print("Nouveaux candidats accessibles :", discovered)
    print("Pays avec sources :", active)
    print("Fichier :", output)
    print("Sources existantes conservées")
    print("Aucune modification de la production")

if __name__ == "__main__":
    main()
