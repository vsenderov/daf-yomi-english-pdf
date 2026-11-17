import { chromium } from 'playwright';
import fs from 'fs';

const [port, tractate, page, out, sidesArg] = process.argv.slice(2);
if (!port || !tractate || !page || !out) {
  console.error('Usage: node render.mjs PORT Tractate Page OUTPREFIX [a,b]');
  process.exit(1);
}

const sides = (sidesArg || 'a,b').split(',').map(s => s.trim()).filter(Boolean);
const settings = JSON.stringify({ edition: 'english' });

const PRINT_CSS = `@media print {
  @page { margin: 0 }
  #daf-content { width: auto !important; height: auto !important; position: static !important; margin: 0 !important; overflow: visible !important }
  .page-sheet { transform: none !important; position: static !important; margin: 20px auto !important }
}`;

const CHROME_CANDIDATES = {
  darwin: [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
  ],
  linux: [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ],
};

function launchOptions() {
  if (process.env.CHROME_PATH) {
    console.log('Using CHROME_PATH', process.env.CHROME_PATH);
    return { executablePath: process.env.CHROME_PATH };
  }
  if (process.env.CHROME_CHANNEL) {
    console.log('Using CHROME_CHANNEL', process.env.CHROME_CHANNEL);
    return { channel: process.env.CHROME_CHANNEL };
  }
  for (const p of CHROME_CANDIDATES[process.platform] || []) {
    if (fs.existsSync(p)) {
      console.log('Using Chrome at', p);
      return { executablePath: p };
    }
  }
  console.log('Using Playwright Chromium');
  return {};
}

const browser = await chromium.launch(launchOptions());
const ctx = await browser.newContext({ viewport: { width: 1400, height: 1800 } });
await ctx.addInitScript(s => localStorage.setItem('vilnaDafSettings', s), settings);

try {
  for (const side of sides) {
    const pg = await ctx.newPage();
    const url = `http://127.0.0.1:${port}/index.html?tractate=${encodeURIComponent(tractate)}&page=${page}&side=${side}`;
    await pg.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await pg.waitForFunction(() => {
      const c = document.querySelector('#daf-core');
      return c && c._vilnaResult;
    }, null, { timeout: 90000 });
    await pg.evaluate(() => document.fonts.ready);
    await pg.waitForTimeout(1500);
    await pg.emulateMedia({ media: 'print' });
    await pg.waitForTimeout(1500);
    const r = await pg.evaluate(() => {
      const e = document.querySelector('.page-sheet');
      if (!e) throw new Error('missing .page-sheet');
      const b = e.getBoundingClientRect();
      return [b.width, b.height];
    });
    await pg.addStyleTag({ content: PRINT_CSS });
    await pg.pdf({
      path: `${out}-${side}.pdf`,
      width: `${Math.ceil(r[0] + 40)}px`,
      height: `${Math.ceil(r[1] + 44)}px`,
      printBackground: true,
    });
    const geo = await pg.evaluate(() => {
      const o = {};
      for (const q of ['.page-sheet', '.daf-header', '.daf-footer', '.catchword', '.daf-bottom-strip']) {
        const e = document.querySelector(q);
        if (e) {
          const b = e.getBoundingClientRect();
          o[q] = [b.left, b.top + scrollY, b.right, b.bottom + scrollY];
        }
      }
      return o;
    });
    fs.writeFileSync(`${out}-${side}.json`, JSON.stringify(geo));
    console.log(side, r);
    console.log(side, 'ok');
    await pg.close();
  }
} finally {
  await browser.close();
}
