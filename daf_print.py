#!/usr/bin/env python3
"""Render Daf Yomi as a readable A4 PDF: Vilna page, then English Gemara."""

from __future__ import annotations

import argparse
import datetime as dt
import functools
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pymupdf as f

import assemble
import typeset_english as te

ROOT = Path(__file__).resolve().parent
VILNA = ROOT / 'vilna-daf'
TRACTATES_PATH = VILNA / 'data' / 'tractates.json'
RENDER_JS = ROOT / 'render.mjs'
PRINT_JS = ROOT / 'print_html.mjs'
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


def copy_fonts(workdir):
    src = te.find_liberation_dir()
    if not src:
        return None
    dest = workdir / 'fonts'
    dest.mkdir(exist_ok=True)
    copied = False
    for fn in src.glob('LiberationSerif-*.ttf'):
        shutil.copy(fn, dest / fn.name)
        copied = True
    return dest if copied else None


def fetch_english_segments(sefaria_name, display_name, page, side):
    """Fetch William Davidson English text, trying Sefaria and display names."""
    errors = []
    for name in (sefaria_name, display_name):
        if not name:
            continue
        ref = f'{name}.{page}{side}'
        try:
            segs, meta = te.fetch_text(ref)
            return ref, segs, meta
        except Exception as e:
            errors.append(f'{ref}: {e}')
    die('Failed to fetch English text from Sefaria:\n  ' + '\n  '.join(errors))


def typeset_side(sefaria_name, display_name, page, side, workdir, font_dir):
    label = f'{display_name} {page}{side}'
    header = f'{label}, English (William Davidson)'
    ref, segs, meta = fetch_english_segments(sefaria_name, display_name, page, side)
    version = meta.get('versionTitle') or te.VERSION
    print(f'Fetched {ref}: {len(segs)} segments, version {version!r}', flush=True)
    html = te.html_page(
        header, segs, font_dir=font_dir,
        font_pt=te.FONT_PT, line_height=te.LINE_HEIGHT, para_gap_em=te.PARA_GAP_EM,
    )
    html_path = workdir / f'{display_name.replace(" ", "_")}-{page}{side}.html'
    pdf_path = workdir / f'{display_name.replace(" ", "_")}-{page}{side}-en.pdf'
    html_path.write_text(html, encoding='utf-8')
    cmd = [
        'node', str(PRINT_JS), str(html_path), str(pdf_path),
        header, header, *te.PRINT_MARGINS,
    ]
    try:
        subprocess.run(cmd, check=True, cwd=str(ROOT))
    except FileNotFoundError:
        die('node is not on PATH. Install Node.js and run ./setup.sh.')
    except subprocess.CalledProcessError as e:
        die(f'print_html.mjs failed with exit code {e.returncode}.')
    doc = f.open(pdf_path)
    n = doc.page_count
    doc.close()
    print(f'Typeset {label}: {n} A4 page{"s" if n != 1 else ""} at {te.FONT_PT} pt', flush=True)
    return pdf_path, n


def render_vilna(vilna_name, page, sides, port, workdir):
    prefix = workdir / f'{vilna_name.replace(" ", "_")}-{page}'
    cmd = [
        'node', str(RENDER_JS),
        str(port), vilna_name, str(page), str(prefix),
        ','.join(sides),
    ]
    try:
        subprocess.run(cmd, check=True, cwd=str(ROOT))
    except FileNotFoundError:
        die('node is not on PATH. Install Node.js and run ./setup.sh.')
    except subprocess.CalledProcessError as e:
        die(f'render.mjs failed with exit code {e.returncode}.')
    paths = []
    for side in sides:
        pdf = Path(f'{prefix}-{side}.pdf')
        if not pdf.is_file():
            die(f'Missing Vilna render for side {side}: {pdf}')
        paths.append(pdf)
    return paths


def render_one(tractates, display_name, page, side_hint, out_dir, port, workdir, font_dir):
    info = resolve_tractate(display_name, tractates)
    sides = sides_for(info, page, side_hint)
    vilna_name = info['name_en']
    sefaria_name = info.get('sefaria_name') or vilna_name
    shown = ' and '.join(f'{display_name} {page}{s}' for s in sides)
    print(f'Rendering {shown} ...', flush=True)

    vilna_paths = render_vilna(vilna_name, page, sides, port, workdir)
    assemble_sides = []
    english_counts = []
    for side, vilna_path in zip(sides, vilna_paths):
        en_path, n = typeset_side(sefaria_name, display_name, page, side, workdir, font_dir)
        label = f'{display_name} {page}{side}'
        assemble_sides.append({
            'label': label,
            'vilna_path': str(vilna_path),
            'english_path': str(en_path),
        })
        english_counts.append((label, n))

    dest = out_dir / f'{output_stem(display_name, page, sides)}.pdf'
    stem_label = f'{display_name} {page}'
    total, _details = assemble.assemble(str(dest), assemble_sides, label=stem_label)
    detail = ', '.join(f'{lab} {n}' for lab, n in english_counts)
    print(
        f'Wrote {dest} ({total} A4 page{"s" if total != 1 else ""}; English: {detail})',
        flush=True,
    )
    return dest, total


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog='daf-print',
        description=(
            'Render Daf Yomi as an A4 PDF: the classic Vilna page, then the '
            'William Davidson English translation of the Gemara.'
        ),
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
    for path in (RENDER_JS, PRINT_JS):
        if not path.is_file():
            die(f'Missing {path.name}. The repository may be incomplete.')


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
            font_dir = copy_fonts(workdir)
            for name, page, side, day in jobs:
                if day is not None:
                    print(f'--- {day.isoformat()}: {name} {page}{side} ---', flush=True)
                written.append(
                    render_one(tractates, name, page, side, out_dir, port, workdir, font_dir)
                )
    finally:
        httpd.shutdown()
        httpd.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
