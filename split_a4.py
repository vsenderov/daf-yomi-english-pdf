#!/usr/bin/env python3
"""Slice tall vilna-daf print PDFs into A4 pages with a repeated header and footer."""

import argparse
import json
import sys

import pymupdf as f

A4W, A4H, M = 595.28, 841.89, 28
PX = 0.75  # CSS pixels to PDF points
PAD = 20 * PX  # matches the 20px print margin in render.mjs


def cuts_for(page, geo):
    """Return (cuts, sx0, sx1, st, hb) in PDF points for one tall amud."""
    s = [v * PX for v in geo['.page-sheet']]
    sx0, sx1 = PAD, PAD + (s[2] - s[0])
    st, sb = PAD, PAD + (s[3] - s[1])
    hb = (geo['.daf-header'][3] + 6) * PX
    k = (A4W - 2 * M) / (sx1 - sx0)
    lines = [l['bbox'] for b in page.get_text('dict')['blocks'] for l in b.get('lines', [])]
    if lines:
        sb = min(sb, max(l[3] for l in lines) + 8)

    def free(y):
        return not any(l[1] + 0.5 < y < l[3] - 0.5 for l in lines)

    avail = (A4H - 2 * M - (hb - st) * k - 18) / k
    cuts, y = [], hb
    while sb - y > avail + 1:
        t = y + avail
        while not free(t):
            t -= 0.5
        cuts.append((y, t))
        y = t
    if any(y < l[1] and l[3] <= sb for l in lines):
        cuts.append((y, sb))
    elif cuts:
        cuts[-1] = (cuts[-1][0], sb)
    else:
        cuts.append((y, sb))
    return cuts, sx0, sx1, st, hb


def append_side(out, pdf_path, json_path, label):
    src = f.open(pdf_path)
    page = src[0]
    with open(json_path, encoding='utf-8') as fh:
        geo = json.load(fh)
    cuts, sx0, sx1, st, hb = cuts_for(page, geo)
    k = (A4W - 2 * M) / (sx1 - sx0)
    n = len(cuts)
    for i, (y0, y1) in enumerate(cuts, 1):
        pg = out.new_page(width=A4W, height=A4H)
        hh = (hb - st) * k
        pg.show_pdf_page(f.Rect(M, M, A4W - M, M + hh), src, 0, clip=f.Rect(sx0, st, sx1, hb))
        bh = (y1 - y0) * k
        pg.show_pdf_page(f.Rect(M, M + hh, A4W - M, M + hh + bh), src, 0, clip=f.Rect(sx0, y0, sx1, y1))
        pg.draw_rect(f.Rect(M, M, A4W - M, M + hh + bh), color=(0, 0, 0), width=1)
        pg.insert_text(
            (M, A4H - M + 4),
            f'{label}, English (William Davidson), page {i} of {n}',
            fontsize=8,
            fontname='helv',
        )
    src.close()
    return n


def merge(output_path, sides):
    """Write an A4 PDF. sides is an iterable of (pdf_path, json_path, label)."""
    out = f.open()
    counts = []
    for pdf_path, json_path, label in sides:
        counts.append(append_side(out, pdf_path, json_path, label))
    out.save(output_path)
    out.close()
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description='Split tall daf PDFs into A4 pages.')
    parser.add_argument('-o', '--output', required=True, help='output A4 PDF path')
    parser.add_argument('items', nargs='+', help='one or more triples: PDF JSON LABEL')
    args = parser.parse_args(argv)
    if len(args.items) % 3 != 0:
        parser.error('arguments must be one or more triples: PDF JSON LABEL')
    sides = list(zip(args.items[0::3], args.items[1::3], args.items[2::3]))
    counts = merge(args.output, sides)
    for (_pdf, _json, label), n in zip(sides, counts):
        print(label, n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
