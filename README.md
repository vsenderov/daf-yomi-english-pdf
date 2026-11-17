# daf-yomi-english-pdf

Render the daily Daf Yomi page as a readable A4 PDF, in the English William Davidson translation, laid out in the classic Vilna format.

The tool serves the open-source [vilna-daf](https://github.com/eladraz/vilna-daf) viewer locally, prints each amud at full height, and splits the tall pages into A4 sheets. The header is repeated on every sheet so you can always see which daf you are on. A footer records the tractate, side, and page number.

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

The first render needs a network connection, because vilna-daf loads the text from Sefaria.

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
```

Each PDF is named like `Bekhorot-60-english.pdf`. The file contains side a, then side b, when both exist. When a tractate ends on an a-side (for example Bekhorot 61a), only that side is rendered, and the file is named `Bekhorot-61a-english.pdf`.

Dates are civil dates in `YYYY-MM-DD` form. With no arguments, the tool uses today's local date. Each date is mapped to its daf through the [Sefaria calendar API](https://www.sefaria.org/api/calendars): `/api/calendars?year=&month=&day=`, using the item whose English title is "Daf Yomi". Multi-word tractate names such as "Bava Metzia" and "Rosh Hashanah" are supported.

## Environment

| Variable | Meaning |
| --- | --- |
| `CHROME_PATH` | Absolute path to a Chrome or Chromium binary. Overrides discovery. |
| `CHROME_CHANNEL` | Playwright browser channel, for example `chrome` or `msedge`. Used only when `CHROME_PATH` is not set. |

Browser selection, in order: `CHROME_PATH`; `CHROME_CHANNEL`; a system install of Google Chrome or Chromium at a standard path (including `/Applications/Google Chrome.app` on macOS); otherwise the Chromium build that `./setup.sh` installed through Playwright.

## Credits and licences

- Page layout and renderer: [eladraz/vilna-daf](https://github.com/eladraz/vilna-daf), included as a git submodule and left unmodified.
- Text and calendar data come from [Sefaria](https://www.sefaria.org/). The English body text is the William Davidson translation. Licence terms for the text are those stated by Sefaria for each work; this repository only automates rendering and does not grant additional rights to the text.

This project's own code is released under the MIT License. See [LICENSE](LICENSE).
