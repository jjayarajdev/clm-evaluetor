// Renders scripts/og-card.html to public/og.png (1200x630) using the repo-root
// Playwright install. Run from website/:  node scripts/render-og.mjs
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(here, 'og-card.html');
const out = path.join(here, '..', 'public', 'og.png');

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
await page.goto('file://' + src, { waitUntil: 'networkidle' });
await page.evaluate(() => document.fonts.ready);
await page.screenshot({ path: out, type: 'png' });
await browser.close();
console.log('wrote', out);
