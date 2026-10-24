#!/usr/bin/env python3
"""Merge two KSEARCHBOT SQLite indexes into a NEW database, never overwrite."""
import argparse
import os
import sqlite3
from pathlib import Path

COLUMNS = ('url', 'host', 'tld', 'title', 'description', 'content', 'crawled_at')
SCHEMA = '''CREATE TABLE pages (
 url TEXT PRIMARY KEY, host TEXT NOT NULL, tld TEXT NOT NULL,
 title TEXT NOT NULL, description TEXT NOT NULL, content TEXT NOT NULL,
 crawled_at INTEGER NOT NULL)'''


def open_source(path):
    if not path.is_file():
        raise ValueError(f'Source absente : {path}')
    con = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    actual = [row[1] for row in con.execute('PRAGMA table_info(pages)')]
    if actual != list(COLUMNS):
        con.close()
        raise ValueError(f'Schéma incompatible : {path}')
    return con


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', required=True, type=Path)
    p.add_argument('--incoming', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    paths = [x.resolve() for x in (args.base, args.incoming, args.output)]
    if len(set(paths)) != 3:
        p.error('Les trois chemins doivent être différents.')
    if args.output.exists():
        p.error('La destination existe déjà : aucun écrasement autorisé.')
    base = incoming = dest = None
    created = False
    try:
        base = open_source(args.base)
        incoming = open_source(args.incoming)
        # Exclusive creation: fail if a file appeared since the existence check.
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        created = True
        dest = sqlite3.connect(args.output)
        dest.execute(SCHEMA)
        dest.execute('CREATE INDEX pages_tld ON pages(tld)')
        insert = '''INSERT INTO pages(url,host,tld,title,description,content,crawled_at)
                    VALUES(?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
                    host=excluded.host,tld=excluded.tld,title=excluded.title,
                    description=excluded.description,content=excluded.content,
                    crawled_at=excluded.crawled_at
                    WHERE excluded.crawled_at >= pages.crawled_at'''
        query = 'SELECT ' + ','.join(COLUMNS) + ' FROM pages'
        for label, source in [('base', base), ('incoming', incoming)]:
            count = 0
            for row in source.execute(query):
                dest.execute(insert, row)
                count += 1
            print(f'{label}: {count} lignes lues')
        dest.commit()
        total = dest.execute('SELECT COUNT(*) FROM pages').fetchone()[0]
        integrity = dest.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity != 'ok':
            raise ValueError(f'Intégrité SQLite invalide : {integrity}')
        print(f'Fusion OK : {total} URL uniques ; {args.output.stat().st_size:,} octets')
    except (sqlite3.Error, OSError, ValueError) as e:
        p.exit(1, f'ERREUR : {e}\n')
    finally:
        for con in (dest, incoming, base):
            if con is not None:
                con.close()
        # Do not delete any file, including an incomplete new output on failure.
        if created and args.output.exists():
            print(f'Fichier créé : {args.output}')


if __name__ == '__main__':
    main()
