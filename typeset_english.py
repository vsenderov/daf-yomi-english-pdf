#!/usr/bin/env python3
"""Fetch William Davidson English Gemara from Sefaria and typeset it as clean A4 HTML."""

from __future__ import annotations

import html as htmlmod
import json
import re
import urllib.parse
import urllib.request
import os
from pathlib import Path

USER_AGENT = 'daf-yomi-english-pdf (https://github.com/vsenderov/daf-yomi-english-pdf)'
SEFARIA_TEXT = (
    'https://www.sefaria.org/api/texts/{ref}'
    '?context=0&commentary=0&ven={version}'
)
VERSION = 'William Davidson Edition - English'

# Default typography for the English A4 pages.
FONT_PT = 9
LINE_HEIGHT = 1.42
PARA_GAP_EM = 0.42
# top, bottom, left, right — passed to print_html.mjs
PRINT_MARGINS = ('16mm', '15mm', '16mm', '16mm')

LIBERATION_DIRS = [
    Path('/usr/share/fonts/truetype/liberation'),
    Path('/usr/share/fonts/liberation'),
    Path('/usr/local/share/fonts/liberation'),
    Path('/opt/homebrew/share/fonts/liberation'),
]


def find_liberation_dir():
    """Return a directory that contains LiberationSerif-Regular.ttf, or None."""
    env = os.environ.get('LIBERATION_FONT_DIR')
    candidates = [Path(env)] if env else []
    candidates.extend(LIBERATION_DIRS)
    for folder in candidates:
        if folder and (folder / 'LiberationSerif-Regular.ttf').is_file():
            return folder
    return None

ALLOWED_TAGS = {'b', 'strong', 'i', 'em', 'br'}
LABEL_RE = re.compile(
    r'^\s*<(strong|b)>\s*(MISHNA|MISHNAH|GEMARA)\s*:?\s*</\1>\s*',
    re.IGNORECASE,
)
TAG_RE = re.compile(r'</?([a-zA-Z][\w:-]*)(?:\s[^>]*)?/?>')
SECTION_MARK_RE = re.compile(r'^§\s*')


def fetch_text(ref, version=VERSION):
    """Return a list of HTML segments for ref, e.g. 'Bekhorot.60a'."""
    url = SEFARIA_TEXT.format(
        ref=urllib.parse.quote(ref),
        version=urllib.parse.quote(version),
    )
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    title = data.get('versionTitle') or ''
    if version.lower() not in title.lower() and data.get('text'):
        # Unexpected version; still use the text but record the title.
        pass
    segs = data.get('text') or []
    if not segs:
        raise RuntimeError(f'No English text returned for {ref} (version {title!r}).')
    return segs, data


def sanitize(fragment):
    def repl(match):
        raw = match.group(0)
        name = match.group(1).lower()
        if name not in ALLOWED_TAGS:
            return ''
        if raw.startswith('</'):
            return f'</{name}>'
        if raw.endswith('/>') or name == 'br':
            return '<br>'
        return f'<{name}>'
    return TAG_RE.sub(repl, fragment)


def parse_segment(raw):
    text = sanitize(raw or '').strip()
    label = None
    section_break = False
    m = LABEL_RE.match(text)
    if m:
        word = m.group(2).upper()
        label = 'Mishna' if word.startswith('MISHNA') else 'Gemara'
        text = text[m.end():].strip()
    if SECTION_MARK_RE.match(text):
        section_break = True
        text = SECTION_MARK_RE.sub('', text).strip()
    return label, section_break, text


def html_page(label, segments, font_dir=None, font_pt=11, line_height=1.48, para_gap_em=0.58):
    """Build a complete HTML document for one amud."""
    font_css = ''
    if font_dir:
        font_dir = Path(font_dir)
        faces = [
            ('LiberationSerif-Regular.ttf', '400', 'normal'),
            ('LiberationSerif-Bold.ttf', '700', 'normal'),
            ('LiberationSerif-Italic.ttf', '400', 'italic'),
            ('LiberationSerif-BoldItalic.ttf', '700', 'italic'),
        ]
        parts = []
        for name, weight, style in faces:
            path = font_dir / name
            if path.is_file():
                parts.append(
                    "@font-face { font-family: 'BodySerif'; "
                    f"src: url('{path.as_uri()}'); font-weight: {weight}; font-style: {style}; }}"
                )
        font_css = '\n'.join(parts)

    family = "'BodySerif', 'Liberation Serif', 'Times New Roman', Times, serif" if font_css else \
        "'Liberation Serif', 'Times New Roman', Times, serif"

    body = []
    for i, raw in enumerate(segments, 1):
        label_word, section_break, text = parse_segment(raw)
        if not text and not label_word:
            continue
        classes = ['seg']
        if section_break:
            classes.append('section-break')
        inner = ''
        if label_word:
            inner += f'<span class="section-label">{htmlmod.escape(label_word)}</span>'
        inner += text
        body.append(
            f'<p class="{" ".join(classes)}" data-n="{i}">'
            f'<span class="segno">{i}</span>{inner}</p>'
        )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{htmlmod.escape(label)}</title>
<style>
{font_css}
html, body {{
  margin: 0;
  padding: 0;
}}
body {{
  font-family: {family};
  font-size: {font_pt}pt;
  line-height: {line_height};
  color: #1a1a1a;
  text-align: justify;
  hyphens: auto;
  -webkit-hyphens: auto;
}}
p.seg {{
  margin: 0 0 {para_gap_em}em 0;
  padding-left: 1.55em;
  position: relative;
  orphans: 2;
  widows: 2;
}}
p.seg.section-break {{
  margin-top: 0.95em;
}}
.segno {{
  position: absolute;
  left: 0;
  top: 0.12em;
  width: 1.3em;
  font-size: {max(font_pt - 3, 6.5)}pt;
  line-height: 1;
  color: #7a7a7a;
  font-family: 'Liberation Sans', Helvetica, sans-serif;
  text-align: right;
  padding-right: 0.25em;
}}
.section-label {{
  display: block;
  font-variant: small-caps;
  letter-spacing: 0.14em;
  font-weight: 700;
  font-size: {max(font_pt - 0.5, 9)}pt;
  text-align: left;
  margin: 0.15em 0 0.4em 0;
  color: #111;
}}
b, strong {{ font-weight: 700; }}
i, em {{ font-style: italic; }}
</style>
</head>
<body>
{''.join(body)}
</body>
</html>
'''
