#!/usr/bin/env node
// Records a captioned screen video of the LOCAL web app (Playwright, from web/node_modules).
// Start the demo first:  node scripts/demo-up.mjs   (and check it with: node scripts/preflight.mjs --running)
//   node scripts/record-demo.mjs [--url http://127.0.0.1:5173] [--user recordRider1] [--out docs/demo]
//                                [--width 390] [--height 844] [--caption-height 96] [--pace 1.5]
// The phone frame in the web app is 390x844 (web/src/app/app.tsx). The video is that frame size plus a caption strip
// below it (--caption-height), so captions never cover the app. --pace scales every pause (default 1.5).
// Only existing elements are tapped; every caption describes what the screen shows. No secrets are read or printed.
// Faving a fact writes one demo row (is_demo); the script unfaves it again before the end.
import { createRequire } from 'node:module';
import { mkdirSync, readdirSync, renameSync } from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const { chromium } = createRequire(path.join(root, 'web', 'package.json'))('playwright');

const argv = process.argv.slice(2);
const flag = (n, d) => { const i = argv.indexOf(`--${n}`); return i >= 0 && argv[i + 1] ? argv[i + 1] : d; };
const URL_ = flag('url', 'http://127.0.0.1:5173');
const USER = flag('user', 'recordRider1');
const OUT = path.resolve(root, flag('out', 'docs/demo'));
const W = Number(flag('width', 390));
const H = Number(flag('height', 844));
const CAP = Number(flag('caption-height', 96));
const PACE = Number(flag('pace', 1.5));
const wait = (page, s) => page.waitForTimeout(Math.round(s * 1000 * PACE));

async function caption(page, text, big = false) {
  await page.evaluate(({ text, big, W, H, CAP }) => {
    let el = document.getElementById('rec-caption');
    if (!el) {
      el = document.createElement('div');
      el.id = 'rec-caption';
      document.body.appendChild(el);
    }
    el.style.cssText = [
      'position:fixed', 'left:0', 'right:0', 'bottom:0', 'z-index:2147483647', 'box-sizing:border-box',
      `height:${big ? H + CAP : CAP}px`, `width:${W}px`, 'padding:12px 16px', 'display:flex', 'align-items:center',
      big ? 'justify-content:center' : 'justify-content:flex-start', 'background:#1D3557', 'color:#FFFFFF',
      'font:600 16px/1.35 Inter,system-ui,sans-serif', big ? 'text-align:center;font-size:20px' : '', 'letter-spacing:.1px',
    ].join(';');
    el.textContent = text;
  }, { text, big, W, H, CAP });
}

async function go(page, hash) { await page.evaluate((h) => { window.location.hash = h; }, hash); }
async function tap(page, locator) {
  if (await locator.count()) { await locator.first().scrollIntoViewIfNeeded().catch(() => {}); await locator.first().click({ timeout: 4000 }).catch(() => {}); return true; }
  return false;
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: W, height: H + CAP },
    recordVideo: { dir: OUT, size: { width: W, height: H + CAP } },
  });
  const page = await context.newPage();
  const t0 = Date.now();
  // The app root is the phone frame at the top; keep the page body from scrolling under the caption strip.
  await page.goto(URL_);
  await page.addStyleTag({ content: `body{padding-bottom:${CAP}px !important;}` });

  // 1 Sign in (a plain stub form: no design yet)
  await caption(page, 'Sign in with a sandbox username. A plain form: this screen has no design yet.');
  await wait(page, 3);
  await page.fill('input', USER);
  await wait(page, 2);
  await page.click('button');

  // 2 Loading
  await wait(page, 1.5);
  await caption(page, 'Boston fun facts while the app loads, each with its source.');
  await wait(page, 4);
  await tap(page, page.getByText('Tap for another fact'));
  await wait(page, 4);

  // 3 Home
  await tap(page, page.getByText('Start exploring'));
  await wait(page, 2);
  await caption(page, 'Home: Park Street from real MBTA stop data in Tiger Data, a stop fact, and your demo rank and points.');
  await wait(page, 5);
  await wait(page, 3);
  await caption(page, 'Fave a fact with the star. It is saved to the database as a demo row.');
  const faved = await tap(page, page.getByLabel('Fave this fun fact'));
  await wait(page, 4);

  // 4 Traveled
  await tap(page, page.locator('a[href="#/traveled"]'));
  if (!faved) await go(page, '#/traveled');
  await wait(page, 1.5);
  await caption(page, 'Traveled: miles per line from check-ins. Zeros for now (no real riders yet). Map art is a placeholder.');
  await wait(page, 6);

  // 5 Explore
  await tap(page, page.locator('a[href="#/explore"]'));
  await wait(page, 2);
  await caption(page, 'Explore: nearby spots at each stop. All spots and labels shown are demo placeholders.');
  await wait(page, 5);
  await caption(page, 'Filter by category, for example Cafés.');
  await tap(page, page.getByRole('button', { name: 'Cafés' }));
  await wait(page, 4);
  await tap(page, page.getByRole('button', { name: 'All', exact: true }));
  await wait(page, 1.5);
  await caption(page, 'And by ownership label. Only declared or certified labels appear; the examples are fictional sample spots.');
  await tap(page, page.getByLabel('Filters'));
  await wait(page, 2);
  await tap(page, page.getByText('Women-owned'));
  await wait(page, 4);
  await tap(page, page.getByText(/^Show \d+ spots?$/));
  await wait(page, 5);

  // 6 Faves
  await tap(page, page.locator('a[href="#/faves"]'));
  await wait(page, 2);
  await caption(page, 'Faves: the facts you saved. Tap the star to unfave.');
  await wait(page, 5);
  await tap(page, page.getByLabel('Unfave this fact')); // leaves no demo row behind
  await wait(page, 3);

  // 7 Profile
  await go(page, '#/home');
  await wait(page, 2);
  await tap(page, page.locator('a[href="#/profile"]'));
  await wait(page, 2);
  await caption(page, 'Profile: rank tiers and demo offers. No real partnerships.');
  await wait(page, 6);
  await wait(page, 5);

  // Closing card
  await caption(page, 'Demo build. Check-in screen design coming. Transit data from the MBTA', true);
  await wait(page, 6);

  const video = page.video();
  await context.close();
  const file = video ? await video.path() : null;
  await browser.close();
  if (file) {
    const dest = path.join(OUT, 'tquest-demo.webm');
    renameSync(file, dest);
    console.log(`video: ${path.relative(root, dest)} (about ${Math.round((Date.now() - t0) / 1000)} s)`);
  } else console.log('no video was produced', readdirSync(OUT));
}
main().catch((e) => { console.error('record-demo failed:', e.message); process.exit(1); });
