# App scope: design inventory, what is built, what is stubbed

> Demo placeholder. No partnership, endorsement or real discount is implied. UI comes only from `design/`.

> **Two clients.** This page describes the React app in `web/`, which is the app we demo and record (Boston GIS maps from `client-bryan/map`, plus the Analytics tab). The earlier vanilla prototype `client-bryan/demo` is documented in `client-bryan/demo/README.md`.

## What exists in `design/`
| File | Contents |
|---|---|
| `canvas/Loading.dc.html` | Loading screen (fun fact, "tap for another fact", start button) |
| `canvas/Main.dc.html` | Home (greeting, rank bar, fact card with dots and star, Park Street map with pins, bottom nav) |
| `canvas/Traveled.dc.html` | Traveled (full-screen map, miles per line legend, unlocked-spot card) |
| `canvas/Explore.dc.html` | Explore (category bubbles, filter sheet, spot cards with promo, owner dots) |
| `canvas/Faves.dc.html` | Faved fun facts |
| `canvas/Profile.dc.html` | User page (rank avatar, points, member pass, perks per rank) |
| `canvas/README.md`, `canvas.json` | Notes and board layout |
| `icons/*.svg`, `tokens/colors.json`, `sketches/*.png` | Nav icons, colors and fonts, original sketches |
| `FIGMA_LINKS.md`, `INTAKE.md` | Link to the private canvas, intake log |

No Figma export, no login, check-in, friends, leaderboard, quests, redemption or store-verification screens exist.

## How designed screens are built
`web/scripts/port-design.mjs` converts each `.dc.html` to a React component so markup and inline styles match the design exactly (run by `npm run port`, also part of `npm run dev` and `npm run build`). Static placeholder text in the design (for example "1,240 pts", "[name]", "7 unlocked!") is replaced by real values; nothing else is changed.

## Screens built from designs (wired to real endpoints)
| Screen | Endpoints |
|---|---|
| Loading | insights `GET /loading-facts` |
| Home (Park Street scene) | data-platform `GET /stops/{id}`; insights `GET /stops/{id}/facts`, `/stops/{id}/content`, `GET /loading-facts`, `GET`/`POST`/`DELETE /me/faves`; game-engine `GET /me/rank`; insights `GET /rank-tiers` |
| Traveled | data-platform `GET /me/travel` |
| Explore | data-platform `GET /stops/{id}`; insights `GET /stops/{id}/nearby` (category and label filters) |
| Faves | insights `GET /me/faves`, `DELETE /me/faves/{id}` |
| Profile | game-engine `GET /me/rank`, `GET /me/points`; insights `GET /rank-tiers`, `GET /offers?rank=`, `/stops/{id}/nearby` (sponsor names) |

## Analytics tab (authored by the admin, not drawn by Isabella)
Added 2026-11-22 as a fourth tab. `design/canvas/Analytics.dc.html` and `design/icons/nav-analytics.svg` were authored by the admin to match the approved canvas: same tokens (`design/tokens/colors.json`), fonts (Space Grotesk, Inter, Caveat, Fredoka), card radius and offset shadow, pill style and bubble nav icon. The nav in Home, Explore, Traveled and Profile was changed from three to four columns (`design/canvas/*.dc.html`), then `web/scripts/port-design.mjs` regenerated the components. Isabella reviewed and approved it.

| Block | Label on screen | Data |
|---|---|---|
| Right now: vehicles per subway line, active alerts, lines affected, feed freshness | Live MBTA data | data-platform `GET /analytics/system` (live `vehicles`, `active_alerts`) |
| Last hours, vehicle reports per line (SVG line chart with a text alternative) | Live MBTA data | same endpoint, from the `vehicles_route_5m` continuous aggregate |
| Busiest and quietest: hour-of-day bars (Boston time), busiest and quietest line | Live MBTA data | same endpoint; thin until more days are collected |
| Your ride insights: stops collected, home line, points, leaderboard place | demo rider data | insights-sponsors `/analytics/me`, game-engine `/me/collection`, `/me/rank`, `/leaderboards` (in-memory demo data) |

If the rider services fail, the live blocks still show and the rider block says it is unavailable. All numbers come from API responses; none is hard-coded.

**Visual-diff check (2026-11-22).** `node scripts/shoot-web.mjs` took 390x844 screenshots of every existing screen before and after the change and `python scripts/visual-diff.py` compared them. Everything above the bottom nav matched (no pixel differences on Loading, Traveled, Explore, Faves and Profile; on Home only a moving train dot on the live map). The only changes are in the nav region. Analytics was compared side by side with Explore and Profile for header, margins, card and pill style.

## Stubs (no design yet; plain page that says "No design yet" and lists endpoints)
| Screen | Endpoints it will use |
|---|---|
| Sign in (functional, plain form) | insights `POST /auth/demo-login` |
| Check in (plain button) | data-platform `GET /stops/{id}`; game-engine `POST /checkins` |
| Friends, leaderboard, quests, redemptions | game-engine `/friends`, `/leaderboards`, `/quests`, `/redemptions`; insights `/offers`, `/physical-rewards/catalog` |

## Gaps and decisions
1. **Maps are placeholders** (Home, Traveled), as in the design README; Bryan rebuilds them from Boston GIS data. Home pins are real content items projected onto the design map around the stop; Traveled draws no pins or segments yet (unlocked spots have no coordinates; segments are returned by the API but not drawn).
2. **No stop picker in the design.** Home is fixed to Park Street (the design scene). Explore and Profile read the four demo stops (Harvard, Davis, Fenway, Kenmore) where the demo spots are.
3. **Explore "Along a line" filter and along-line ordering are not built** (no API); the options are omitted. **"Ethnic Boston" switch** is inert: it needs inferred ethnicity data, which our label policy forbids (see issue #45).
4. **Explore sections:** the design's "Recommended for you" and "Popular along the Green Line" need personalization and direction-of-travel data we do not have, so one plain "Explore" section lists the spots. "Sightseeing" has no spot category, so it is empty.
5. **Owner filters** use only the four options in the design (Locally, Latinx, Women, Black-owned) mapped to `local-independent`, `latino-owned`, `woman-owned`, `african-american-owned`. The other five labels have no design.
6. **Honesty over copy:** the design cards say "LOCALLY OWNED". The app shows that badge only when the API returns a declared or certified `local-independent` label; every other demo spot shows "Demo". Design copy that implies real partnerships ("partnered stores") remains in Profile; we flag it for Isabella and cover it with the demo footer.
7. **Loading and error states** have no design; they are minimal unstyled status boxes ("…", the error text, "Retry").
8. The design's fictional example stores (Abuela's Kitchen and others) are not used; spots come from the API (demo placeholders and fictional "Sample ... (demo)" spots).
9. The nav has no link to the check-in stub or the "more" stub; reach them at `#/checkin` and `#/more`.
