#!/usr/bin/env python3
"""Assemble a linear A4 PDF: each Vilna amud, then its English pages."""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf as f

A4W, A4H = 595.28, 841.89
MM = 72 / 25.4  # points per millimetre
FOOTER_Y = A4H - 22
FOOTER_SIZE = 8
FOOTER_COLOR = (0.18, 0.18, 0.18)
DEFAULT_MARGIN_MM = 8
DEFAULT_FOOTER_BAND_MM = 10


def centered_text(page, y, text, fontsize, fontname, color=(0, 0, 0)):
    width = f.get_text_length(text, fontname=fontname, fontsize=fontsize)
    x = (A4W - width) / 2
    page.insert_text((x, y), text, fontsize=fontsize, fontname=fontname, color=color)


def sheet_clip(page, pad=1.5):
    """Return a clip rect around the printed page-sheet frame, if one exists."""
    frames = []
    for d in page.get_drawings():
        r = d.get('rect')
        if d.get('type') == 's' and r is not None and r.width > 400 and r.height > 500:
            frames.append(r)
    if frames:
        r = max(frames, key=lambda box: box.width * box.height)
        return f.Rect(r.x0 - pad, r.y0 - pad, r.x1 + pad, r.y1 + pad)
    # Fallback: ink union (text plus drawings), which still drops empty margins.
    xs, ys = [], []
    for b in page.get_text('dict')['blocks']:
        xs += [b['bbox'][0], b['bbox'][2]]
        ys += [b['bbox'][1], b['bbox'][3]]
    for d in page.get_drawings():
        r = d.get('rect')
        if r:
            xs += [r.x0, r.x1]
            ys += [r.y0, r.y1]
    if not xs:
        return page.rect
    return f.Rect(min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def place_vilna_filled(dst, src_doc, src_index, margin_mm=DEFAULT_MARGIN_MM,
                       footer_band_mm=DEFAULT_FOOTER_BAND_MM):
    """Clip to the page-sheet and scale up to fill A4, leaving a footer band."""
    margin = margin_mm * MM
    footer = footer_band_mm * MM
    clip = sheet_clip(src_doc[src_index])
    avail_w = A4W - 2 * margin
    avail_h = A4H - margin - footer
    scale = min(avail_w / clip.width, avail_h / clip.height)
    w, h = clip.width * scale, clip.height * scale
    x = (A4W - w) / 2
    y = margin + max(0, (avail_h - h) / 2)
    dest = f.Rect(x, y, x + w, y + h)
    dst.show_pdf_page(dest, src_doc, src_index, clip=clip)
    return dest, scale, clip


def place_page(dst, src_doc, src_index):
    """Draw a source page onto dst, scaled to fit A4 (never upscaled past 1)."""
    src = src_doc[src_index]
    sr = src.rect
    scale = min(A4W / sr.width, A4H / sr.height, 1.0)
    w, h = sr.width * scale, sr.height * scale
    x = (A4W - w) / 2
    y = (A4H - h) / 2.0
    dest = f.Rect(x, y, x + w, y + h)
    dst.show_pdf_page(dest, src_doc, src_index)
    return dest


def add_vilna_page(out, vilna_doc, vilna_index, note, margin_mm=DEFAULT_MARGIN_MM):
    page = out.new_page(width=A4W, height=A4H)
    dest, scale, clip = place_vilna_filled(page, vilna_doc, vilna_index, margin_mm=margin_mm)
    if note:
        centered_text(page, FOOTER_Y, note, FOOTER_SIZE, 'helv', FOOTER_COLOR)
    return {'dest': dest, 'scale': scale, 'clip': clip}


def add_english_page(out, english_doc, english_index):
    page = out.new_page(width=A4W, height=A4H)
    place_page(page, english_doc, english_index)
    return page


def assemble(output, sides, label=None, margin_mm=DEFAULT_MARGIN_MM):
    """Write a SinglePage A4 PDF.

    sides is an iterable of dicts with keys:
      label         – footer on the Vilna sheet, e.g. 'Bekhorot 60a'
      vilna_path    – path to a rendered Vilna PDF (one page, or use vilna_index)
      vilna_index   – page index in that PDF (default 0)
      english_path  – path to the typeset English PDF for that amud
    """
    sides = list(sides)
    if not sides:
        raise ValueError('assemble() needs at least one amud.')
    if not label:
        label = sides[0]['label'].rstrip('ab').strip()

    out = f.open()
    details = []
    for side in sides:
        vdoc = f.open(side['vilna_path'])
        vindex = side.get('vilna_index', 0)
        info = add_vilna_page(out, vdoc, vindex, side['label'], margin_mm=margin_mm)
        info['label'] = side['label']
        vdoc.close()

        edoc = f.open(side['english_path'])
        n_en = edoc.page_count
        for i in range(n_en):
            add_english_page(out, edoc, i)
        edoc.close()
        info['english_pages'] = n_en
        details.append(info)
        print(
            f"Vilna {side['label']}: clip {info['clip'].width:.1f}x{info['clip'].height:.1f} pt, "
            f"scale {info['scale']:.4f} "
            f"({info['dest'].width:.1f}x{info['dest'].height:.1f} pt on the A4 sheet)",
            flush=True,
        )

    out.set_pagelayout('SinglePage')
    out.set_pagemode('UseNone')
    out.set_metadata({
        'title': f'{label} — Vilna page and English translation',
        'author': 'daf-yomi-english-pdf',
        'subject': 'Linear A4 sequence: each Vilna amud, then its William Davidson English pages',
        'creator': 'daf-print',
    })
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    n = out.page_count
    out.save(output)
    out.close()
    return n, details


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description='Assemble Vilna and English A4 pages into one PDF.')
    p.add_argument('-o', '--output', required=True)
    p.add_argument('--label')
    p.add_argument(
        'items', nargs='+',
        help='one or more triples: VILNA_PDF ENGLISH_PDF LABEL',
    )
    args = p.parse_args(argv)
    if len(args.items) % 3 != 0:
        p.error('arguments must be one or more triples: VILNA_PDF ENGLISH_PDF LABEL')
    sides = []
    for vilna, english, label in zip(args.items[0::3], args.items[1::3], args.items[2::3]):
        sides.append({'vilna_path': vilna, 'english_path': english, 'label': label})
    n, details = assemble(args.output, sides, label=args.label)
    print(f'Wrote {args.output} ({n} pages, PageLayout=SinglePage)')
    for d in details:
        print(f"{d['label']}: English {d['english_pages']} page{'s' if d['english_pages'] != 1 else ''}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
