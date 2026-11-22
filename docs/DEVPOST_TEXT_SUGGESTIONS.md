# Suggested Devpost text edits for the Analytics tab

Suggestions only. Nothing here has been applied to Devpost; read it, edit it, and paste what you approve. Every claim below is true of the repo and the running demo as of 2026-11-22. Numbers in the Tiger Data section come from `docs/TIGER_DATA_RESULTS.md`; the Analytics screen itself shows live numbers that change, so do not copy them into the text.

## Project story: "What it does" (add one bullet, and change the Home bullet)
Replace the first bullet with:
- **Live Boston map:** real MBTA lines, stations and live trains from our Tiger Data database, a 2D/3D toggle with landmark buildings from Boston open data, and tappable spots with a fact (and source) each. Tap in at a station and the ride is checked against the real MBTA schedule.

Add after "Explore":
- **Analytics (live MBTA data):** a tab that shows what the T is doing right now, computed from the data we collect: vehicles per subway line, active alerts and which lines they affect, vehicle reports per hour for each line over the last hours, and the busiest and quietest hours and lines. These come from a continuous aggregate in Tiger Data. A separate block shows demo rider insights (stops collected, home line, points, leaderboard place), clearly labeled as demo data from synthetic riders, not real people.

## "How we built it" (add to the Tiger Data bullet)
- The Analytics tab reads one new endpoint, `GET /analytics/system`, which runs a handful of read-only queries against the `vehicles_route_5m` continuous aggregate and the live `vehicles` table in a single database round trip.

## "Tiger Data results" (keep as is; optional sentence)
- The same continuous aggregate that gave the 84.2x speedup in our benchmark now powers the live Analytics tab, so the number is not just a benchmark: the app reads from it.

## "Challenges" (optional bullet)
- Designing a screen with no existing design: the admin authored the Analytics tab and its nav icon from the approved canvas tokens and verified with a before/after screenshot diff that no existing screen changed except the nav. It still needs Isabella's review.
- The hour-of-day chart is thin until the collector has run for more days; the screen says how many hours and days it covers.

## "What's next" (add)
- Review of the Analytics tab by the designer, more days of collected data for the hour-of-day view, and rider insights computed from real rides once there are real riders.

## Image gallery
Upload the new screenshots from `docs/screenshots/` (all eight). Suggested order: `07-analytics.png`, `02-home.png`, `08-analytics-insights.png`, `03-traveled.png`, `04-explore.png`, `06-profile.png`, `05-faves.png`, `01-loading.png`. Suggested captions:
- `07-analytics.png`: Analytics: live MBTA data, vehicles per line right now and vehicle reports per hour
- `08-analytics-insights.png`: Analytics: busiest and quietest hours, then demo rider insights (labeled demo data)
- `02-home.png`: Home: rank, a stop fact and the live Boston map with MBTA lines and trains
- `03-traveled.png`: Traveled: the real network with miles per line and unlocked spots
- `04-explore.png`: Explore: nearby spots and perks from fictional demo businesses
- `06-profile.png`: Profile: rank and demo perks
- `05-faves.png`: Faves: facts you starred
- `01-loading.png`: Loading: a Boston fun fact with its source

## Video
Upload the new video (`docs/demo/tquest-demo.webm`, or the MP4) and use the new unlisted link. If it was recorded outside MBTA service hours, the "Ride there" step shows "no train is scheduled at this hour" instead of a verified ride; re-record in the daytime with `node scripts/record-demo.mjs` if you want the verified ride in the video.

## Things not to claim
- No real partnerships, discounts or ownership labels; all sponsors, stores and labels are demo placeholders.
- No real riders: rider data on the screen is synthetic demo data.
- Not deployed: it runs locally.
