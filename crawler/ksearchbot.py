#!/usr/bin/env python3
"KSEARCHBOT: crawler national indépendant. Python 3.10+."
import argparse
import ipaddress
import json
import logging
import re
import socket
import sqlite3
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
from safe_http import create_session
from bs4 import BeautifulSoup

from frontier_discovery import save_discovered_links

ROOT = Path(__file__).resolve().parent.parent / 'search'
DB = ROOT / 'data' / 'index.sqlite'
AGENT = 'KSEARCHBOT/1.0 (+https://kgstudio.fr/search/; contact: contact@kgstudio.fr)'
LOG = logging.getLogger('ksearchbot')


def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('''CREATE TABLE IF NOT EXISTS pages (
        url TEXT PRIMARY KEY, host TEXT NOT NULL, tld TEXT NOT NULL,
        title TEXT NOT NULL, description TEXT NOT NULL, content TEXT NOT NULL,
        crawled_at INTEGER NOT NULL)''')
    con.execute('CREATE INDEX IF NOT EXISTS pages_tld ON pages(tld)')
    con.commit()
    return con


def safe_host(host):
    if not host or host.lower() == 'localhost' or host.endswith('.local'):
        return False
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(item[4][0]).is_global for item in addresses)
    except (OSError, ValueError):
        return False


def normalize(url, tld):
    try:
        p = urlsplit(url.strip())
        host = (p.hostname or '').lower().rstrip('.')
        if p.scheme not in ('http', 'https') or p.username or p.password or p.port not in (None, 80, 443):
            return None
        if not host.endswith('.' + tld) or host == '.' + tld:
            return None
        if re.search(r'\.(pdf|jpg|jpeg|png|gif|svg|zip|mp4|mp3|webp|css|js|xml)$', p.path, re.I):
            return None
        return urlunsplit((p.scheme, host, p.path or '/', p.query, ''))
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser(description='Indexation autonome par extension nationale')
    ap.add_argument('--country', required=True, help='Code ISO du pays, ex: FR')
    ap.add_argument('--seed', action='append', required=True, help='URL de départ; option répétable')
    ap.add_argument('--max-pages', type=int, default=100)
    ap.add_argument('--delay', type=float, default=2.0, help='Délai minimal entre requêtes par hôte')
    ap.add_argument('--max-depth', type=int, default=2)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    countries = {c['code']: c['tld'].lower() for c in json.loads((ROOT / 'countries.json').read_text())}
    tld = countries.get(args.country.upper())
    if not tld:
        ap.error('Code pays absent de countries.json')
    if not 1 <= args.max_pages <= 100000 or args.delay < 1 or not 0 <= args.max_depth <= 20:
        ap.error('max-pages >= 1, delay >= 1, max-depth entre 0 et 20')
    queue = deque((u, 0) for s in args.seed if (u := normalize(s, tld)))
    if not queue:
        ap.error('Aucune URL de départ avec extension .' + tld)
    con = init_db()
    session = create_session()
    session.headers.update({'User-Agent': AGENT, 'Accept': 'text/html,application/xhtml+xml'})
    session.trust_env = False
    robots = {}
    visited = set()
    last_request = {}
    indexed = 0
    while queue and indexed < args.max_pages:
        url, depth = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        host = urlsplit(url).hostname
        if not safe_host(host):
            LOG.warning('Hôte non public ou inaccessible: %s', host)
            continue
        if host not in robots:
            rp = RobotFileParser()
            rp.set_url('https://' + host + '/robots.txt')
            try:
                # Pas de redirections automatiques; vérification réseau avant chaque accès.
                rr = session.get(rp.url, timeout=10, allow_redirects=False)
                rp.parse(rr.text.splitlines() if rr.status_code == 200 else ['User-agent: *', 'Disallow: /'] if rr.status_code in (401, 403) or rr.status_code >= 500 else [])
            except requests.RequestException:
                rp.parse(['User-agent: *', 'Disallow: /'])
            robots[host] = rp
        rp = robots[host]
        if not rp.can_fetch(AGENT, url):
            LOG.info('Robots interdit: %s', url)
            continue
        wait = max(args.delay, rp.crawl_delay(AGENT) or 0)
        time.sleep(max(0, last_request.get(host, 0) + wait - time.monotonic()))
        last_request[host] = time.monotonic()
        try:
            response = session.get(url, timeout=12, allow_redirects=False, stream=True)
            if response.status_code != 200 or 'text/html' not in response.headers.get('Content-Type', '').lower():
                response.close()
                continue
            if int(response.headers.get('Content-Length', '0')) > 2_000_000:
                response.close()
                continue
            raw = response.raw.read(2_000_001, decode_content=True)
            response.close()
            if len(raw) > 2_000_000:
                continue
            soup = BeautifulSoup(raw, 'html.parser')
            if soup.find('meta', attrs={'name': re.compile('^robots$', re.I), 'content': re.compile('noindex', re.I)}):
                continue
            title = soup.title.get_text(' ', strip=True) if soup.title else host
            meta = soup.find('meta', attrs={'name': re.compile('^description$', re.I)})
            desc = (meta.get('content', '') if meta else '').strip()
            links = [a.get('href') for a in soup.find_all('a', href=True)] if depth < args.max_depth else []
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
                tag.decompose()
            content = ' '.join(soup.get_text(' ', strip=True).split())[:30000]
            if not desc:
                desc = content[:250]
            con.execute('''INSERT INTO pages(url,host,tld,title,description,content,crawled_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
                title=excluded.title,description=excluded.description,content=excluded.content,crawled_at=excluded.crawled_at''',
                (url, host, tld, title[:250], desc[:500], content, int(time.time())))
            con.commit()
            indexed += 1

            try:
                discovery = save_discovered_links(
                    url,
                    raw.decode(
                        response.encoding or 'utf-8',
                        errors='replace'
                    )
                )
                LOG.info(
                    'Liens découverts : %d, nouveaux : %d',
                    discovery['discovered'],
                    discovery['added']
                )
            except Exception as exc:
                LOG.warning(
                    'Découverte non bloquante pour %s : %s',
                    url,
                    exc
                )

            LOG.info('[%d/%d] %s', indexed, args.max_pages, url)
            for href in links:
                target = normalize(urljoin(url, href), tld)
                if target and target not in visited:
                    queue.append((target, depth + 1))
        except (requests.RequestException, ValueError, OSError) as exc:
            LOG.warning('Échec %s : %s', url, exc)
    LOG.info('Terminé : %d pages indexées.', indexed)


if __name__ == '__main__':
    main()
