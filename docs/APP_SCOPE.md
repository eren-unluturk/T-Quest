# App scope: design inventory, what is built, what is stubbed

> Demo placeholder. No partnership, endorsement or real discount is implied. UI comes only from `design/`.

> **Two clients.** This page describes the React port in `web/`. The app we demo is `client-bryan/demo` (vanilla JS + MapLibre, Boston GIS maps, ride verification), documented in `client-bryan/demo/README.md` and `docs/DEMO.md`. Since issue #80 the maps in `web/` Home and Traveled are the real GIS maps too (mounted from `client-bryan/map`); the placeholder-map notes below date from before that.

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
