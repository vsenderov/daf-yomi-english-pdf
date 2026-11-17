# daf-yomi-english-pdf

Render the daily Daf Yomi as a readable A4 PDF. Each daf is a linear sequence of pages:

1. The classic Vilna page for amud a, enlarged to fill the sheet.
2. The William Davidson English translation of the Gemara for amud a, typeset as a single column (9 point by default; see `--font-size`).
3. The Vilna page for amud b.
4. The English for amud b.

There is no title page. The reader opens the file in single-page view (`/PageLayout` is `SinglePage`). Each Vilna sheet has a short footer naming the amud. When the PDF is made for a calendar date (today, a given day, or a range), that study date is added to the footer on every Vilna and English page, for example "Bekhorot 60a · Daf Yomi, Tuesday 17 November 2026". With `--daf` and no date, the footer names only the amud. When a tractate ends on an a-side (for example Bekhorot 61a), only that side is rendered.

The Vilna page is produced by the open-source [vilna-daf](https://github.com/eladraz/vilna-daf) viewer, in its default Aramaic edition, with the surrounding commentaries in place. The English pages are typeset from the [Sefaria](https://www.sefaria.org/) text API (`/api/texts/...`), using the William Davidson Edition. Dates are resolved through the [Sefaria calendar API](https://www.sefaria.org/api/calendars).

A labelled map of the Vilna page — header, Gemara, Rashi, Tosafot, and the margin notes — is in [docs/vilna-page-guide.pdf](docs/vilna-page-guide.pdf) ([preview](docs/vilna-page-guide.png)). The colours follow the actual regions of Bekhorot 60a.

## Requirements

- Git
- Node.js 18 or newer
- Python 3.9 or newer
- A Chromium-based browser. The setup script installs Playwright's Chromium automatically. To use a browser you already have, set `CHROME_PATH`.

## Setup

```bash
git clone --recurse-submodules https://github.com/vsenderov/daf-yomi-english-pdf.git
cd daf-yomi-english-pdf
./setup.sh
```

If you already cloned without submodules:

```bash
git submodule update --init --recursive
./setup.sh
```

`setup.sh` installs Node dependencies, Playwright's Chromium, and the Python package `pymupdf` into a local `.venv`.

The first render needs a network connection, because vilna-daf and the English typesetter both load text from Sefaria.

## Usage

```bash
# Today's Daf Yomi (your local civil date)
./daf-print

# A specific date
./daf-print 2026-11-20

# An inclusive date range (one PDF per date)
./daf-print 2026-11-17 2026-11-23

# A specific daf, both sides (or only the side you name)
./daf-print --daf Bekhorot 60
./daf-print --daf Bava Metzia 10
./daf-print --daf Bekhorot 61a

# Choose the output directory (default: ./out)
./daf-print -o ~/Documents/daf

# English body size in points (default: 9). Segment numbers and section
# labels scale with it. The environment variable DAF_FONT_PT is used when
# the flag is omitted.
./daf-print --font-size 9
```

Each PDF is named like `Bekhorot-60-english.pdf`. The file contains side a, then side b, when both exist. When a tractate ends on an a-side (for example Bekhorot 61a), only that side is rendered, and the file is named `Bekhorot-61a-english.pdf`.

Dates are civil dates in `YYYY-MM-DD` form. With no arguments, the tool uses today's local date. Each date is mapped to its daf through the [Sefaria calendar API](https://www.sefaria.org/api/calendars): `/api/calendars?year=&month=&day=`, using the item whose English title is "Daf Yomi". Multi-word tractate names such as "Bava Metzia" and "Rosh Hashanah" are supported.

## Environment

| Variable | Meaning |
| --- | --- |
| `CHROME_PATH` | Absolute path to a Chrome or Chromium binary. Overrides discovery. |
| `CHROME_CHANNEL` | Playwright browser channel, for example `chrome` or `msedge`. Used only when `CHROME_PATH` is not set. |
| `LIBERATION_FONT_DIR` | Directory containing `LiberationSerif-Regular.ttf`. Used for the English body if present; otherwise the browser falls back to Times. |
| `DAF_FONT_PT` | English body size in points when `--font-size` is not given. The default is 9. |

Browser selection, in order: `CHROME_PATH`; `CHROME_CHANNEL`; a system install of Google Chrome or Chromium at a standard path (including `/Applications/Google Chrome.app` on macOS); otherwise the Chromium build that `./setup.sh` installed through Playwright.

## Credits and licences

- Vilna page layout and renderer: [eladraz/vilna-daf](https://github.com/eladraz/vilna-daf), included as a git submodule and left unmodified.
- English body text and calendar data come from [Sefaria](https://www.sefaria.org/). The English is the William Davidson translation of the Gemara, without Rashi, Tosafot, or the margin notes (those remain on the Vilna page). Licence terms for the text are those stated by Sefaria for each work; this repository only automates rendering and does not grant additional rights to the text.

This project's own code is released under the MIT License. See [LICENSE](LICENSE).
