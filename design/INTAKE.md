# Design intake log

Sketches (`design/sketches/`) and Figma (`FIGMA_LINKS.md`, `tokens/`) are the only source of truth for UI. For each sketch/screen, log what it implies for the API and which contract it needs. Do not invent screens.

| Date | Source (file or Figma link) | Screen/element | Data it implies | Contract needed | Issue # |
|---|---|---|---|---|---|
| 2026-11-21 | design/sketches/2026-11-21-ui-workflow.png | Loading screen: a fun fact on every tap | random loading_screen facts | data-platform: GET /facts (requested) | #43 |
| 2026-11-21 | design/sketches/2026-11-21-ui-workflow.png | Traveled map: already-traveled T segments vs unexplored area | per-user traveled segments | data-platform: GET /me/travel (requested) | #43 |
| 2026-11-21 | design/sketches/2026-11-21-ui-workflow.png | Miles traveled card: miles per line (Green, Red, Blue tiles) | per-user miles per line | data-platform: GET /me/travel (requested) | #43 |
| 2026-11-21 | design/sketches/2026-11-21-ui-workflow.png | Explore: routes, stops, stores; store info from the person's data and sponsorships | recommendations | insights-sponsors recs (draft OpenAPI, #26) | #44 |
| 2026-11-21 | design/sketches/2026-11-21-ui-workflow.png | Explore filters: sightseeing, Boston tourist stops, restaurants, drinks, partnered stores; chips; ethnic Boston recs switch; ownership dots; fun fact per place | store categories, ownership tags, store fun fact | insights-sponsors (requested) | #44, #45 |
| 2026-11-21 | design/sketches/2026-11-21-ui-workflow.png | Home: profile + points bar, "fact about this place" card (dots, learn more), map with pins, bottom nav (this page, explore, traveled) | points, rank, nearest stop facts | game-engine /me/points, /me/rank; data-platform /stops/{id} | #42 |
| 2026-11-21 | design/sketches/2026-11-21-ui-workflow.png | User page: rank avatar, points bar to next rank, total miles, show page to partnered stores for patches and stickers | rank name/avatar/next rank, miles, collection, redemptions | game-engine /me/rank, /me/collection, /redemptions; data-platform /me/travel | #42, #43 |
| 2026-11-21 | design/sketches/2026-11-21-ui-workflow.png | Ranks: Patriot, Boston Lobstah, Children of Liberty, Tea Party Raider, Midnight Rider, Lamplighter, Town Crier, Harbor Seal; rank changes the profile picture | 8 named tiers + avatar | game-engine (requested) | #42, #45 |
