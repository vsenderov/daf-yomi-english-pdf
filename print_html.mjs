import { chromium } from 'playwright';
import path from 'path';
import { pathToFileURL } from 'url';
import { launchOptions } from './chrome.mjs';

const [htmlPath, pdfPath, header, footerLabel, marginTop, marginBottom, marginLeft, marginRight, footerSuffix] = process.argv.slice(2);
if (!htmlPath || !pdfPath || !header || !footerLabel) {
  console.error('Usage: node print_html.mjs HTML PDF HEADER FOOTER_LABEL [top] [bottom] [left] [right] [footerSuffix]');
  process.exit(1);
}
const margins = {
  top: marginTop || '16mm',
  bottom: marginBottom || '15mm',
  left: marginLeft || '16mm',
  right: marginRight || '16mm',
};

const headerTemplate = `
  <div style="font-size:9pt; font-family: 'Liberation Serif', Times, serif; color:#333;
              width:100%; text-align:center; padding:0 12mm;">
    ${header}
  </div>`;

const footerTemplate = `
  <div style="font-size:8pt; font-family: 'Liberation Serif', Times, serif; color:#333;
              width:100%; text-align:center; padding:0 12mm;">
    ${footerLabel}, page <span class="pageNumber"></span> of <span class="totalPages"></span>${footerSuffix || ''}
  </div>`;

const browser = await chromium.launch(launchOptions());
try {
  const page = await browser.newPage();
  const url = pathToFileURL(path.resolve(htmlPath)).href;
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
  await page.pdf({
    path: pdfPath,
    format: 'A4',
    printBackground: true,
    displayHeaderFooter: true,
    headerTemplate,
    footerTemplate,
    margin: margins,
  });
  console.log('Wrote', pdfPath);
} finally {
  await browser.close();
}
