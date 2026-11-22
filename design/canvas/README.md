# T-Quest design canvas (approved demo, 2026-11-21)

Isabella's approved UI demo. This is the source of truth for the client screens (see AGENTS.md "UI rule").

- Live, clickable canvas: https://claude.ai/artifact/3kA1AWDV675w7jFiyCFssi (private to Isabella until she shares it)
- Original sketch: design/sketches/2026-11-21-ui-workflow.png
- Palette and fonts: design/tokens/colors.json

The `.dc.html` files are the canvas source (one file per screen, 390x844 phone frame). They need the canvas runtime to render, so open the link above to see them. Read them for exact layout, copy, colors and interactions: markup is plain HTML with inline styles, and the `renderVals()` script at the bottom of each file holds the demo data and behavior.

## Screens

| File | Screen | What it does |
|---|---|---|
| Loading.dc.html | Loading | Navy screen, tap for another fun fact, "Start exploring" |
| Main.dc.html | Home | Greeting, points bar, fact card, map around the current stop. Tap a spot on the map: it grows and the yellow card shows its fact (dots page through several). A spot with no fact shows "No history recorded yet" plus a fact about the area nearby. Star in the card faves the fact; star top right opens Faves |
| Traveled.dc.html | Traveled | Full-screen T map: traveled segments solid, untraveled dotted in the line's color. Unlocked spots as yellow check pins (tap for name). Top legend: total miles plus miles per line |
| Explore.dc.html | Explore (one page) | Category bubbles that scroll sideways (All, Sightseeing, Restaurants, Drinks, Cafes, Shopping). Filter button opens a sheet: along a line, owned by (locally, Latinx, women, Black-owned), Ethnic Boston switch, Clear all / Show N spots. Then sideways-scrolling partner rows with promos: "Recommended for you" (with the reason) and "Popular along the Green Line" (direction of travel, closest first, "behind you" last). Ethnic Boston on adds a third row |
| Faves.dc.html | Faved fun facts | Opened from the star on Home, Traveled, Explore. Tap a star to unfave |
| Profile.dc.html | User page | Rank avatar and name, points as a T line, "Show this page at partnered stores to get your prizes" with a member pass, sideways perks for the user's rank ("15% off for Boston Lobstahs"), one locked perk for the next rank |

Bottom nav on every screen: Home, Explore, Traveled, drawn as bubble icons from Isabella's sketch (design/sketches/2026-11-21-nav-buttons.png): a shamrock with HOME under it, a magnifying glass with EXPLORE arched around it, a sailboat with TRAVELED painted on the hull. SVGs in design/icons/. All three are the same size and level. The current page's icon sits on a colored blob (green, yellow, light blue) with a sparkle and wiggles; the others float gently; tap squishes, hover lifts. Animations are off for users with reduced motion. The avatar on Home opens the user page.

## Placeholders

- The two maps (Home and Traveled) are placeholders: client-bryan will rebuild them from Boston GIS data, keeping the pins, line styles and legend described above.

- Partner stores and their offers are FICTIONAL demo businesses (Abuela's Kitchen, Steep & Swirl Tea Bar, Old Brick Walking Tours, Harborlight Books, Roxbury Roots Cafe, Copley Corner Bakery, Pho Lantern, Sabor del Barrio). Eren will replace them with the real example stores; for the demo, locally owned places are preferred.
- Points, miles, usernames, member numbers and anything in [brackets] are placeholders. Real values come from the APIs (rank thresholds: game-engine PR #46).
- Facts about real places (Park Street, Granary, State House, etc.) are real but must be shown with source attribution from the content API (#56).
- Black-owned blue (#457B9D) is a placeholder color; Ethnic Boston behavior is a proposal (#45).
