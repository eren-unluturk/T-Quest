#!/usr/bin/env node
// Takes still screenshots of the LOCAL demo app (client-bryan/demo) for the README and Devpost, 3:2 (1350x900) with the
// phone frame centered. Start the demo first: node scripts/demo-up.mjs. Overwrites docs/screenshots/*.png.
//   node scripts/screenshots-demo.mjs [--url http://localhost:4321] [--out docs/screenshots]
// Needs internet (map tiles, MBTA schedule) and Playwright from web/node_modules. Restart demo-up before running so the
// ride earns points. Faves and rides stay in the browser; nothing is written to the database. No secrets are read.
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const { chromium } = createRequire(path.join(root, 'web', 'package.json'))('playwright');
const argv = process.argv.slice(2);
const flag = (n, d) => { const i = argv.indexOf(`--${n}`); return i >= 0 && argv[i + 1] ? argv[i + 1] : d; };
const URL_ = flag('url', 'http://localhost:4321');
const OUT = path.resolve(root, flag('out', 'docs/screenshots'));

const tap = async (l) => { if (await l.count()) { await l.first().click({ timeout: 5000 }).catch(() => {}); return true; } return false; };
const go = (page, h) => page.evaluate((x) => { window.location.hash = x; }, h);

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1350, height: 900 } })).newPage();
const shot = async (name) => { await page.waitForTimeout(1500); await page.screenshot({ path: path.join(OUT, name) }); console.log('saved', name); };

await page.goto(URL_);
await page.waitForSelector('#start:not([disabled])', { timeout: 90000 });
await shot('01-loading.png');
await tap(page.locator('#start'));
await page.waitForSelector('#tapin', { timeout: 60000 });
await page.waitForTimeout(4000);
await shot('02-home-map.png');
await tap(page.locator('#tilt'));
await page.waitForTimeout(3500);
await shot('03-home-3d.png');
await tap(page.locator('#tilt'));
await tap(page.locator('.pin'));
await tap(page.locator('#fave'));
await tap(page.locator('#tapin'));
await page.waitForTimeout(1500);
await tap(page.locator('[data-to]').nth(1));
await shot('04-tap-in-sheet.png');
await tap(page.locator('#ride'));
await page.waitForSelector('.stampwrap', { timeout: 40000 }).catch(() => {});
await shot('05-ride-verified.png');
await tap(page.locator('#again'));
await tap(page.locator('a[data-tab="traveled"]'));
await page.waitForTimeout(3000);
await shot('06-traveled.png');
await tap(page.locator('a[data-tab="explore"]'));
await page.waitForTimeout(2500);
await shot('07-explore.png');
await tap(page.locator('#filter'));
await shot('08-explore-filters.png');
await tap(page.locator('#show'));
await go(page, '#/home');
await page.waitForSelector('#tapin', { timeout: 30000 });
await tap(page.locator('a[aria-label="Your faved fun facts"]'));
await shot('09-faves.png');
await go(page, '#/home');
await page.waitForSelector('#tapin', { timeout: 30000 });
await tap(page.locator('a[aria-label="Open your user page"]'));
await page.waitForTimeout(1500);
await shot('10-user-page.png');
await browser.close();
