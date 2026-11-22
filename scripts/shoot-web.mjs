#!/usr/bin/env node
// Screenshots every screen of the React web app (http://127.0.0.1:5173) at the design frame size (390x844 frame,
// 430x900 viewport, element screenshot of the frame only) into a folder. Used for the before/after visual diff
// and for the README screenshots.
//   node scripts/shoot-web.mjs --out .work/baseline [--screens loading,home,traveled,explore,faves,profile]
//                              [--url http://127.0.0.1:5173] [--user shotUser1] [--wait 7]
// Needs the demo running (node scripts/demo-up.mjs) and internet for the map tiles. Playwright comes from web/node_modules.
// Faves is shot after one fact is starred on Home, then unstarred again (leaves no demo row). No secrets are read.
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const { chromium } = createRequire(path.join(root, 'web', 'package.json'))('playwright');
const argv = process.argv.slice(2);
const flag = (n, d) => { const i = argv.indexOf(`--${n}`); return i >= 0 && argv[i + 1] ? argv[i + 1] : d; };
const OUT = path.resolve(root, flag('out', '.work/after'));
const URL_ = flag('url', 'http://127.0.0.1:5173');
const USER = flag('user', 'shotUser1');
const WAIT = Number(flag('wait', 7)) * 1000;
const SCREENS = flag('screens', 'loading,home,traveled,explore,faves,profile').split(',');
const NAMES = { loading: '01-loading', home: '02-home', traveled: '03-traveled', explore: '04-explore', faves: '05-faves', profile: '06-profile', analytics: '07-analytics', 'analytics-insights': '08-analytics-insights' };

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 430, height: 1000 } })).newPage();
await page.goto(URL_);
await page.fill('input', USER);
await page.click('button');
await page.waitForTimeout(1500);
const shot = async (key) => {
  // the 390-wide phone frame is the first child div with that width
  const frame = page.locator('div').filter({ has: page.locator('nav, h1, p') }).locator('xpath=self::div[contains(@style,"390px")]').first();
  const target = (await frame.count()) ? frame : page.locator('body');
  await target.screenshot({ path: path.join(OUT, `${NAMES[key] ?? key}.png`) });
  console.log('saved', `${NAMES[key] ?? key}.png`);
};
for (const key of SCREENS) {
  if (key === 'faves') {
    await page.evaluate(() => { window.location.hash = '#/home'; });
    await page.waitForTimeout(WAIT);
    const star = page.getByLabel('Fave this fun fact');
    if (await star.count()) await star.first().click().catch(() => {});
    await page.waitForTimeout(1000);
  }
  await page.evaluate((k) => { window.location.hash = '#/' + k; }, key);
  await page.waitForTimeout(key === 'loading' ? 2500 : WAIT);
  await shot(key);
  if (key === 'analytics') {
    await page.evaluate(() => { const el = [...document.querySelectorAll('div')].find((d) => getComputedStyle(d).overflowY === 'auto' && d.scrollHeight > d.clientHeight); if (el) el.scrollTop = el.scrollHeight; });
    await page.waitForTimeout(600);
    await shot('analytics-insights');
  }
  if (key === 'faves') {
    const un = page.getByLabel('Unfave this fact');
    if (await un.count()) await un.first().click().catch(() => {});
  }
}
await browser.close();
