#!/usr/bin/env python3
"""Run KSEARCHBOT for configured countries in bounded, rotating batches."""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--max-pages', type=int, default=20)
    parser.add_argument('--max-depth', type=int, default=1)
    parser.add_argument('--delay', type=float, default=2.0)
    parser.add_argument('--batch-number', type=int, default=None,
                        help='Zero-based batch number; defaults to rotating daily batch')
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 248 or not 1 <= args.max_pages <= 1000:
        parser.error('Invalid batch-size or max-pages')
    if not 0 <= args.max_depth <= 20 or args.delay < 1:
        parser.error('max-depth must be 0..20 and delay >= 1')

    countries = json.loads((ROOT / 'search/countries.json').read_text(encoding='utf-8'))
    runtime_seeds = ROOT / 'crawler/runtime_seeds.json'
    seeds_path = runtime_seeds if runtime_seeds.exists() else ROOT / 'crawler/seeds.json'
    seeds = json.loads(seeds_path.read_text(encoding='utf-8'))
    codes = [country['code'] for country in countries]
    if args.batch_number is None:
        # Daily rotation only among countries with configured HTTPS seeds.
        codes = [
            code for code in codes
            if isinstance(seeds.get(code), list)
            and any(
                isinstance(url, str) and url.startswith('https://')
                for url in seeds[code]
            )
        ]
    if not codes:
        print('No configured HTTPS seeds: nothing to crawl', flush=True)
        return 0
    batch_count = (len(codes) + args.batch_size - 1) // args.batch_size
    batch_number = (dt.date.today().toordinal() if args.batch_number is None
                    else args.batch_number) % batch_count
    selected = codes[batch_number * args.batch_size:(batch_number + 1) * args.batch_size]
    print(f'Batch {batch_number + 1}/{batch_count}; countries: {", ".join(selected)}', flush=True)
    attempted = 0
    failures = 0
    for code in selected:
        urls = seeds.get(code, [])
        if not isinstance(urls, list):
            print(f'Invalid seeds for {code}', file=sys.stderr, flush=True)
            failures += 1
            continue
        urls = [u for u in urls if isinstance(u, str) and u.startswith('https://')]
        if not urls:
            print(f'Skip {code}: no configured HTTPS seeds', flush=True)
            continue
        cmd = [sys.executable, str(ROOT / 'crawler/ksearchbot.py'),
               '--country', code, '--max-pages', str(args.max_pages),
               '--max-depth', str(args.max_depth), '--delay', str(args.delay)]
        for url in urls:
            cmd.extend(['--seed', url])
        print(f'Running {code}: {len(urls)} seeds', flush=True)
        attempted += 1
        try:
            result = subprocess.run(cmd, cwd=ROOT, check=False, timeout=900)
            if result.returncode:
                failures += 1
                print(f'Crawler failed for {code}: exit {result.returncode}', file=sys.stderr, flush=True)
        except subprocess.TimeoutExpired:
            failures += 1
            print(f'Crawler timed out for {code}', file=sys.stderr, flush=True)
    print(f'Finished: attempted={attempted}, failures={failures}', flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
