#!/usr/bin/env node
// Records a captioned screen video of the LOCAL React app (web/, http://127.0.0.1:5173), using Playwright from
// web/node_modules. Start everything first:  node scripts/demo-up.mjs   then check:  node scripts/preflight.mjs --running
//   node scripts/record-demo.mjs [--url http://127.0.0.1:5173] [--out docs/demo] [--pace 1.0] [--user recordRider1]
//                                [--width 430] [--height 884] [--caption-height 96]
// The phone frame is 390x844 (web/src/app/app.tsx). The video is that frame plus a caption strip below it, so captions
// never cover the app. --pace scales every pause. Needs internet (map tiles, MBTA schedule). Only existing elements
// are tapped, and captions that depend on an outcome (a ride verified or rejected) are chosen from what the screen shows.
// Faving a fact writes one demo row (is_demo); the script unfaves it again. Rides use game-engine's in-memory mode.
// The output file is overwritten on every run (no old copies kept). No secrets are read or printed.
import { createRequire } from 'node:module';
import { mkdirSync, renameSync, rmSync } from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const { chromium } = createRequire(path.join(root, 'web', 'package.json'))('playwright');

const argv = process.argv.slice(2);
const flag = (n, d) => { const i = argv.indexOf(`--${n}`); return i >= 0 && argv[i + 1] ? argv[i + 1] : d; };
const URL_ = flag('url', 'http://127.0.0.1:5173');
const USER = flag('user', 'recordRider1');
const OUT = path.resolve(root, flag('out', 'docs/demo'));
const W = Number(flag('width', 430));
const H = Number(flag('height', 884));
const CAP = Number(flag('caption-height', 96));
const PACE = Number(flag('pace', 1.0));
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
const nav = (page, name) => tap(page.locator(`nav a[aria-label="${name}"]`));
const bodyText = async (page) => (await page.locator('body').innerText().catch(() => '')).replace(/\s+/g, ' ');
const scrollInner = (page, to) => page.evaluate((to) => {
  const el = [...document.querySelectorAll('div')].find((d) => getComputedStyle(d).overflowY === 'auto' && d.scrollHeight > d.clientHeight);
  if (el) el.scrollTo({ top: to === 'end' ? el.scrollHeight : to, behavior: 'smooth' });
}, to);

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: W, height: H + CAP }, recordVideo: { dir: OUT, size: { width: W, height: H + CAP } } });
  const page = await context.newPage();
  const t0 = Date.now();
  await page.goto(URL_);

  // 1 Sign in (a plain stub form: no design yet)
  await caption(page, 'Sign in with a sandbox username. A plain form: this screen has no design yet.');
  await wait(page, 2.5);
  await page.fill('input', USER);
  await wait(page, 1.5);
  await page.click('button');

  // 2 Loading
  await page.waitForSelector('text=Start exploring', { timeout: 30000 });
  await caption(page, 'Boston fun facts while the app loads, each with its source.');
  await wait(page, 3);
  await tap(page.getByText('Tap for another fact'));
  await wait(page, 3);
  await tap(page.getByText('Start exploring'));

  // 3 Home
  await page.waitForSelector('text=Tap in at', { timeout: 60000 });
  await wait(page, 3);
  await caption(page, 'Home: your rank and points, a stop fact, and a live Boston map with MBTA lines and trains from Tiger Data.');
  await wait(page, 7);
  await caption(page, 'Star a fact to save it to Faves.');
  await tap(page.getByLabel('Fave this fun fact'));
  await wait(page, 3);

  // 4 Tap in, ride, verify
  await caption(page, 'Tap in at a station and choose where you get off.');
  await tap(page.getByText(/Tap in at/));
  await wait(page, 4);
  await tap(page.getByText('South Station'));
  await wait(page, 2);
  await caption(page, 'Ride there skips the clock to the next real scheduled train, then checks the ride.');
  await tap(page.getByText('Ride there'));
  await page.waitForSelector('text=/VERIFIED|No scheduled/i', { timeout: 40000 }).catch(() => {});
  await wait(page, 2);
  const t1 = await bodyText(page);
  if (/RIDE\s*VERIFIED/i.test(t1) && !/NOT\s*VERIFIED/i.test(t1)) {
    const pts = t1.match(/\+(\d+)/);
    await caption(page, `Ride verified against the real MBTA schedule${pts ? `; game-engine awards +${pts[1]} points (demo mode)` : ''}.`);
  } else if (/No scheduled/i.test(t1)) {
    // overnight there are no scheduled trains, so there is nothing to verify; say so instead of showing a failure unexplained
    await caption(page, 'No train is scheduled at this hour, so Ride there has nothing to verify.');
  } else if (/NOT\s*VERIFIED/i.test(t1)) {
    await caption(page, 'This demo ride was not verified (the app checks the real MBTA schedule).');
  }
  await wait(page, 5);
  if (/No scheduled/i.test(t1)) { await tap(page.getByLabel('Cancel ride')); await wait(page, 1); } else await tap(page.getByText('Back to map'));
  await wait(page, 2);
  await caption(page, 'Tap in again, but tap out instantly, as a GPS spoofer would.');
  await tap(page.getByText(/Tap in at/));
  await wait(page, 3);
  await tap(page.getByText('Tap out now'));
  await page.waitForSelector('text=/NOT\\s*VERIFIED/i', { timeout: 30000 }).catch(() => {});
  await wait(page, 1.5);
  if (/NOT\s*VERIFIED/i.test(await bodyText(page))) await caption(page, 'Rejected: no train is that fast, so no points.');
  await wait(page, 5);
  await tap(page.getByText('Back to map'));
  await wait(page, 1);

  // 5 Traveled
  await nav(page, 'Traveled');
  await caption(page, 'Traveled: the real MBTA network, with miles per line and unlocked spots as you ride.');
  await page.waitForTimeout(3500);
  await wait(page, 7);

  // 6 Explore
  await nav(page, 'Explore');
  await caption(page, 'Explore: nearby spots and perks from fictional demo businesses. No real partnerships.');
  await page.waitForTimeout(2500);
  await wait(page, 5);
  await tap(page.getByRole('button', { name: 'Cafés' }));
  await wait(page, 3);
  await tap(page.getByRole('button', { name: 'All', exact: true }));
  await wait(page, 1);

  // 7 Faves
  await tap(page.getByLabel('Your faved fun facts'));
  await caption(page, 'Faves: the facts you starred.');
  await page.waitForTimeout(2000);
  await wait(page, 4);
  await tap(page.getByLabel('Unfave this fact')); // leaves no demo row behind
  await wait(page, 2);

  // 8 Profile
  await page.evaluate(() => { window.location.hash = '#/profile'; });
  await caption(page, 'Profile: rank and demo perks. Offers are placeholders; no real discounts or partners.');
  await page.waitForTimeout(3000);
  await wait(page, 6);

  // 9 Analytics
  await nav(page, 'Analytics');
  await page.waitForSelector('text=Right now', { timeout: 40000 }).catch(() => {});
  await wait(page, 1);
  await caption(page, 'Analytics, live MBTA data from Tiger Data: vehicles per line right now, active alerts and feed freshness.');
  await wait(page, 6);
  await scrollInner(page, 330);
  await caption(page, 'Vehicle reports per hour for each line, from the continuous aggregate behind the vehicle feed.');
  await wait(page, 6);
  await scrollInner(page, 760);
  await caption(page, 'Busiest and quietest hours, from the hours collected so far.');
  await wait(page, 6);
  await scrollInner(page, 'end');
  await caption(page, 'Your ride insights are demo rider data, not real people.');
  await wait(page, 6);

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
