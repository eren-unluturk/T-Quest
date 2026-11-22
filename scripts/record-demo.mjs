#!/usr/bin/env node
// Records a captioned screen video of the LOCAL demo app (client-bryan/demo, with the Boston maps), using Playwright
// from web/node_modules. Start everything first:  node scripts/demo-up.mjs   then check:  node scripts/preflight.mjs --running
//   node scripts/record-demo.mjs [--url http://localhost:4321] [--out docs/demo] [--pace 1.2]
//                                [--width 460] [--height 892] [--caption-height 96]
// The phone frame is 390x844 with a 24 px page margin (client-bryan/demo/public/style.css). The video is that frame
// (viewport 460x892) plus a caption strip below it, so captions never cover the app. --pace scales every pause.
// Needs internet (map tiles, MBTA schedule). Only existing elements are tapped, and captions that depend on an outcome
// (a ride verified or rejected) are chosen from what the screen actually shows. The ride and check-in only touch
// game-engine's in-memory mode; faves and rides live in the browser's localStorage, so nothing is written to the database.
// The output file is overwritten on every run (no old copies kept). No secrets are read or printed.
import { createRequire } from 'node:module';
import { mkdirSync, renameSync, rmSync } from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const { chromium } = createRequire(path.join(root, 'web', 'package.json'))('playwright');

const argv = process.argv.slice(2);
const flag = (n, d) => { const i = argv.indexOf(`--${n}`); return i >= 0 && argv[i + 1] ? argv[i + 1] : d; };
const URL_ = flag('url', 'http://localhost:4321');
const OUT = path.resolve(root, flag('out', 'docs/demo'));
const W = Number(flag('width', 460));
const H = Number(flag('height', 892));
const CAP = Number(flag('caption-height', 96));
const PACE = Number(flag('pace', 1.2));
const wait = (page, s) => page.waitForTimeout(Math.round(s * 1000 * PACE));

async function caption(page, text, big = false) {
  await page.evaluate(({ text, big, W, H, CAP }) => {
    let el = document.getElementById('rec-caption');
    if (!el) { el = document.createElement('div'); el.id = 'rec-caption'; document.body.appendChild(el); }
    el.style.cssText = [
      'position:fixed', 'left:0', 'right:0', 'bottom:0', 'z-index:2147483647', 'box-sizing:border-box',
      `height:${big ? H + CAP : CAP}px`, `width:${W}px`, 'padding:12px 20px', 'display:flex', 'align-items:center',
      big ? 'justify-content:center' : 'justify-content:flex-start', 'background:#1D3557', 'color:#FFFFFF',
      'font:600 16px/1.35 Inter,system-ui,sans-serif', big ? 'text-align:center;font-size:22px' : '',
    ].join(';');
    el.textContent = text;
  }, { text, big, W, H, CAP });
}

async function tap(locator, timeout = 5000) {
  if (await locator.count()) { await locator.first().click({ timeout }).catch(() => {}); return true; }
  return false;
}
const go = (page, hash) => page.evaluate((h) => { window.location.hash = h; }, hash);
const stampText = async (page) => (await page.locator('.stampwrap').innerText().catch(() => '')).replace(/\s+/g, ' ');

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: W, height: H + CAP }, recordVideo: { dir: OUT, size: { width: W, height: H + CAP } } });
  const page = await context.newPage();
  const t0 = Date.now();
  await page.goto(URL_);
  await page.addStyleTag({ content: `body{padding-bottom:${CAP}px !important;}` });

  // 1 Loading
  await caption(page, 'Boston fun facts while the app loads.');
  await page.waitForSelector('#start:not([disabled])', { timeout: 90000 });
  await wait(page, 3);
  await tap(page.locator('#next'));
  await wait(page, 4);
  await tap(page.locator('#start'));

  // 2 Home: map with live stations and trains
  await page.waitForSelector('#tapin', { timeout: 60000 });
  await wait(page, 3);
  await caption(page, 'Home: a Boston map with live MBTA stations and trains from Tiger Data.');
  await wait(page, 7);
  await tap(page.locator('#tilt'));
  await wait(page, 1.5);
  await caption(page, '3D landmark buildings from Boston open data.');
  await wait(page, 5);
  await tap(page.locator('#tilt'));
  await wait(page, 2);
  await caption(page, 'Tap a spot on the map for a fact about it.');
  await tap(page.locator('.pin'));
  await wait(page, 5);
  await caption(page, 'Star a fact to save it to Faves (kept in this browser).');
  await tap(page.locator('#fave'));
  await wait(page, 4);

  // 3 Tap in, ride, verify
  await caption(page, 'Tap in at a station, then choose where you get off.');
  await tap(page.locator('#tapin'));
  await wait(page, 4);
  await tap(page.locator('[data-to]').nth(1)); // second stop in the list (South Station from Park Street)
  await wait(page, 3);
  await caption(page, 'Ride there skips the clock to the next real scheduled train, then checks the ride.');
  await tap(page.locator('#ride'));
  await page.waitForSelector('.stampwrap', { timeout: 40000 }).catch(() => {});
  await wait(page, 2);
  const st = await stampText(page);
  if (/RIDE VERIFIED/.test(st)) {
    const pts = st.match(/\+(\d+)/);
    await caption(page, `Ride verified against the real MBTA schedule${pts ? `; game-engine awards +${pts[1]} points (demo mode)` : ''}.`);
  } else if (st) {
    await caption(page, 'This demo ride was not verified (the app checks the real MBTA schedule).');
  }
  await wait(page, 7);
  await tap(page.locator('#again'));
  await wait(page, 3);

  // 3b a spoofed tap-out is rejected
  await caption(page, 'Tap in again, but tap out instantly, as a GPS spoofer would.');
  await tap(page.locator('#tapin'));
  await wait(page, 4);
  await tap(page.locator('#now'));
  await page.waitForSelector('.stampwrap', { timeout: 40000 }).catch(() => {});
  await wait(page, 2);
  const st2 = await stampText(page);
  if (/NOT VERIFIED/.test(st2)) await caption(page, 'Rejected: no train is that fast, so no points.');
  await wait(page, 6);
  await tap(page.locator('#again'));
  await wait(page, 2);

  // 4 Traveled
  await tap(page.locator('a[data-tab="traveled"]'));
  await page.waitForTimeout(2500);
  await caption(page, 'Traveled: your verified rides and unlocked spots. Rides are kept in this browser (demo).');
  await wait(page, 9);

  // 5 Explore
  await tap(page.locator('a[data-tab="explore"]'));
  await page.waitForTimeout(2500);
  await caption(page, 'Explore: nearby spots and perks from fictional demo businesses. No real partnerships.');
  await wait(page, 7);
  await tap(page.locator('[data-cat]').nth(2));
  await wait(page, 4);
  await tap(page.locator('[data-cat]').first());
  await wait(page, 1.5);
  await caption(page, 'Filter by line and ownership label (demo data).');
  await tap(page.locator('#filter'));
  await wait(page, 3);
  await tap(page.locator('[data-own]').first());
  await wait(page, 3);
  await tap(page.locator('#show'));
  await wait(page, 5);

  // 6 Faves
  await go(page, '#/home');
  await page.waitForSelector('#tapin', { timeout: 30000 });
  await tap(page.locator('a[aria-label="Your faved fun facts"]'));
  await page.waitForTimeout(2000);
  await caption(page, 'Faves: the facts you starred.');
  await wait(page, 6);

  // 7 User page
  await go(page, '#/home');
  await page.waitForSelector('#tapin', { timeout: 30000 });
  await tap(page.locator('a[aria-label="Open your user page"]'));
  await page.waitForTimeout(2500);
  await caption(page, 'Your user page: rank and points from game-engine (demo mode), and demo perks.');
  await wait(page, 8);

  // closing card
  await caption(page, 'Demo build. Check-in screen design coming. Transit data from the MBTA', true);
  await wait(page, 6);

  const video = page.video();
  await context.close();
  const file = video ? await video.path() : null;
  await browser.close();
  if (!file) { console.error('no video was produced'); process.exit(1); }
  const dest = path.join(OUT, 'tquest-demo.webm');
  rmSync(dest, { force: true });
  renameSync(file, dest);
  console.log(`video: ${path.relative(root, dest)} (about ${Math.round((Date.now() - t0) / 1000)} s)`);
}
main().catch((e) => { console.error('record-demo failed:', e.message); process.exit(1); });
