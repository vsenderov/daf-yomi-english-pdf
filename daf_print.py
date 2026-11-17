#!/usr/bin/env python3
"""Render Daf Yomi pages as readable A4 PDFs in the English William Davidson edition."""

from __future__ import annotations

import argparse
import datetime as dt
import functools
import http.server
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import split_a4

ROOT = Path(__file__).resolve().parent
VILNA = ROOT / 'vilna-daf'
TRACTATES_PATH = VILNA / 'data' / 'tractates.json'
RENDER_JS = ROOT / 'render.mjs'
SEFARIA_CALENDAR = 'https://www.sefaria.org/api/calendars?year={year}&month={month}&day={day}'
USER_AGENT = 'daf-yomi-english-pdf (https://github.com/vsenderov/daf-yomi-english-pdf)'

# Sefaria calendar spellings that differ from vilna-daf's name_en.
ALIASES = {
    'bekhorot': 'Bechorot',
    'bechorot': 'Bechorot',
    'arakhin': 'Arachin',
    'arachin': 'Arachin',
    'berakhot': 'Berachot',
    'berachot': 'Berachot',
    'eruvin': 'Eiruvin',
    'eiruvin': 'Eiruvin',
}

DAF_RE = re.compile(r'^(.+?)\s+(\d+)([ab])?$', re.IGNORECASE)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


def die(msg, code=1):
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def parse_date(s):
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        die(f'Invalid date {s!r}. Use YYYY-MM-DD.')


def parse_daf_string(s):
    text = ' '.join(s.replace('.', ' ').split())
    m = DAF_RE.match(text)
    if not m:
        die(f'Could not parse daf {s!r}. Examples: Bekhorot 60, "Bava Metzia 10", Bekhorot 61a.')
    name, page, side = m.group(1), int(m.group(2)), (m.group(3) or '').lower()
    return name, page, side


def load_tractates():
    if not TRACTATES_PATH.is_file():
        die(
            'vilna-daf is missing or incomplete. Run ./setup.sh, or:\n'
            '  git submodule update --init --recursive'
        )
    with open(TRACTATES_PATH, encoding='utf-8') as fh:
        return json.load(fh)


def resolve_tractate(name, tractates):
    key = name.strip().lower()
    for t in tractates:
        if t['name_en'].lower() == key or t['sefaria_name'].lower() == key:
            return t
    alias = ALIASES.get(key)
    if alias:
        for t in tractates:
            if t['name_en'].lower() == alias.lower():
                return t
    known = ', '.join(t['name_en'] for t in tractates)
    die(f'Unknown tractate {name!r}. Known names include: {known}.')


def sides_for(info, page, side_hint):
    if side_hint in ('a', 'b'):
        return [side_hint]
    sides = ['a']
    if page < info['last_page'] or info.get('ends_on_b', True):
        sides.append('b')
    first = info.get('first_page', 2)
    if page < first or page > info['last_page']:
        die(f"{info['name_en']} has pages {first} to {info['last_page']}; got {page}.")
    return sides


def fetch_calendar(day):
    url = SEFARIA_CALENDAR.format(year=day.year, month=day.month, day=day.day)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except urllib.error.URLError as e:
        die(f'Failed to reach the Sefaria calendar API: {e}')
    for item in data.get('calendar_items') or []:
        title = item.get('title')
        en = title.get('en') if isinstance(title, dict) else title
        if en == 'Daf Yomi':
            display = item.get('displayValue')
            label = display.get('en') if isinstance(display, dict) else display
            ref = item.get('ref') or label
            if not ref:
                die(f'Sefaria Daf Yomi item for {day.isoformat()} has no ref.')
            return ref
    die(f'Sefaria calendar for {day.isoformat()} has no Daf Yomi item.')


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def start_server(port):
    handler = functools.partial(QuietHandler, directory=str(VILNA))
    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def output_stem(display_name, page, sides):
    safe = display_name.replace(' ', '-')
    if sides == ['a', 'b']:
        return f'{safe}-{page}-english'
    return f'{safe}-{page}{sides[0]}-english'


def render_one(tractates, display_name, page, side_hint, out_dir, port, workdir):
    info = resolve_tractate(display_name, tractates)
    sides = sides_for(info, page, side_hint)
    vilna_name = info['name_en']
    prefix = workdir / f'{vilna_name.replace(" ", "_")}-{page}'
    cmd = [
        'node',
        str(RENDER_JS),
        str(port),
        vilna_name,
        str(page),
        str(prefix),
        ','.join(sides),
    ]
    env = os.environ.copy()
    shown = ' and '.join(f'{display_name} {page}{s}' for s in sides)
    print(f'Rendering {shown} ...', flush=True)
    try:
        subprocess.run(cmd, check=True, cwd=str(ROOT), env=env)
    except FileNotFoundError:
        die('node is not on PATH. Install Node.js and run ./setup.sh.')
    except subprocess.CalledProcessError as e:
        die(f'render.mjs failed with exit code {e.returncode}.')

    side_args = []
    labels = []
    for side in sides:
        pdf = Path(f'{prefix}-{side}.pdf')
        geo = Path(f'{prefix}-{side}.json')
        if not pdf.is_file() or not geo.is_file():
            die(f'Missing render output for side {side}: {pdf} / {geo}')
        label = f'{display_name} {page}{side}'
        side_args.append((str(pdf), str(geo), label))
        labels.append(label)

    dest = out_dir / f'{output_stem(display_name, page, sides)}.pdf'
    counts = split_a4.merge(str(dest), side_args)
    total = sum(counts)
    detail = ', '.join(f'{lab} {n}' for lab, n in zip(labels, counts))
    print(f'Wrote {dest} ({total} A4 page{"s" if total != 1 else ""}; {detail})', flush=True)
    return dest, total


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog='daf-print',
        description='Render Daf Yomi (English, William Davidson) as A4 PDFs.',
        epilog='With no arguments, print today\'s Daf Yomi. Pass one date, or a start and end date.',
    )
    p.add_argument('dates', nargs='*', help='YYYY-MM-DD, or a start and end date')
    p.add_argument(
        '--daf',
        nargs='+',
        metavar='NAME',
        help='a specific daf, for example: Bekhorot 60, or Bava Metzia 10',
    )
    p.add_argument('-o', '--output-dir', default='./out', help='output directory (default: ./out)')
    return p.parse_args(argv)


def jobs_from_args(args, tractates):
    if args.daf and args.dates:
        die('Pass either dates or --daf, not both.')
    if args.daf:
        name, page, side = parse_daf_string(' '.join(args.daf))
        # Keep the user-facing spelling in the filename and footer.
        return [(name, page, side, None)]
    if len(args.dates) > 2:
        die('Pass zero, one, or two dates.')
    if not args.dates:
        days = [dt.date.today()]
    elif len(args.dates) == 1:
        days = [parse_date(args.dates[0])]
    else:
        start, end = parse_date(args.dates[0]), parse_date(args.dates[1])
        if end < start:
            die('The end date is before the start date.')
        days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    jobs = []
    for day in days:
        ref = fetch_calendar(day)
        name, page, side = parse_daf_string(ref)
        jobs.append((name, page, side, day))
    return jobs


def ensure_ready():
    if not VILNA.joinpath('index.html').is_file():
        die(
            'vilna-daf is missing or incomplete. Run ./setup.sh, or:\n'
            '  git submodule update --init --recursive'
        )
    if not (ROOT / 'node_modules' / 'playwright').exists():
        die('Playwright is not installed. Run ./setup.sh first.')


def main(argv=None):
    args = parse_args(argv)
    ensure_ready()
    tractates = load_tractates()
    jobs = jobs_from_args(args, tractates)
    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    port = free_port()
    httpd = start_server(port)
    written = []
    try:
        with tempfile.TemporaryDirectory(prefix='daf-print-') as tmp:
            workdir = Path(tmp)
            for name, page, side, day in jobs:
                if day is not None:
                    print(f'--- {day.isoformat()}: {name} {page}{side} ---', flush=True)
                written.append(render_one(tractates, name, page, side, out_dir, port, workdir))
    finally:
        httpd.shutdown()
        httpd.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
