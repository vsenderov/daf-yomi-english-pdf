import { chromium } from 'playwright';
import { launchOptions } from './chrome.mjs';

const [port, tractate, page, out, sidesArg] = process.argv.slice(2);
if (!port || !tractate || !page || !out) {
  console.error('Usage: node render.mjs PORT Tractate Page OUTPREFIX [a,b]');
  process.exit(1);
}

const sides = (sidesArg || 'a,b').split(',').map(s => s.trim()).filter(Boolean);
const settings = JSON.stringify({ edition: 'aramaic' });

// Print the page-sheet at its native size. The assembler later clips the
// stroked frame and scales it up to fill an A4 sheet. Disabling the viewer's
// print transform avoids shrinking the daf to the Letter-intersect-A4 safe
// area and then enlarging it again.
const PRINT_CSS = `@media print {
  @page { margin: 0 }
  #daf-content { width: auto !important; height: auto !important; position: static !important; margin: 0 !important; overflow: visible !important }
  .page-sheet { transform: none !important; position: static !important; margin: 20px auto !important }
}`;

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
    // The catchword is filled in asynchronously after the main layout.
    await pg.waitForTimeout(1500);
    await pg.emulateMedia({ media: 'print' });
    await pg.waitForTimeout(500);
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
    console.log(side, r, 'ok');
    await pg.close();
  }
} finally {
  await browser.close();
}
