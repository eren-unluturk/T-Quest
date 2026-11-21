# T-Quest: Project Brief

Boston Hacks, Transit Gamification track + "Best Use of Tiger Data" subtrack.

**T-Quest** is a Pokemon-Go-style gamification layer over the MBTA (subway AND bus). Daily commuting is mundane, and nothing is gained when the T breaks. Riding becomes gameplay.

## Core loop
- Check in at stops/stations, collect them, build routes (Strava-style route tracking), earn points.
- Points level a travel rank. Rank determines discount tier (rank 1 ~5%, increasing; top ranks can unlock free items).

## Sponsors
- Food spots and clothing stores near stops get native placements (stop "local picks", sponsored quests), NOT pop-up ads.
- High-rank users redeem discounts. Sports teams/merch (e.g. Red Sox hat, ticket discounts) are redeemable with points.

## Physical rewards
Users can redeem stickers and patches from partner stores to put on their bag, so accomplishments show up in the real world (a patch for completing a line, a Freedom Trail sticker, a rank patch), plus other physical media incentives from sponsors.
- Each physical reward maps to a digital badge/achievement.
- Redemption is verified at the store (single-use code or QR scanned/entered by staff), with limited per-store inventory, per-user limits, and rank/achievement requirements.
- Modeled in data only: `physical_rewards`, `badges`, `redemptions` (status: issued, claimed, expired), `store_inventory`, and a user collection/bag of earned badges (`user_collections`). No UI decisions.

## Social
Friends, leaderboards, comparing points with friends. Rewards and points tracker.

## Disruptions
Delay/cancellation/outage notifications. If a long-time user of a line (their "home line", e.g. Green) has an outage, grant compensation points.

## Tourist layer
Per-stop fast facts, Freedom Trail spots, Boston history, loading-screen fun facts.

## Analytics and recommendations
Route analytics: where you've been, Boston analytics, AI-assisted recommendations of new routes/neighborhoods to explore (sponsorship room).

## Consent
Opt-in cookie/location tracking of other places visited (restaurants etc.), with explicit consent, to improve recommendations.

## Tiger Data (our prize angle)
Tiger Data (Postgres + TimescaleDB) is the core store: rider events as a hypertable, continuous aggregates (leaderboards, home-line detection, personal stats), compression for high-volume MBTA realtime data, `time_bucket` analytics, SQL-based recommendations. We plan to show performance numbers in the demo: compression ratio and aggregate query latency.

## Data sources
MBTA V3 API (static + realtime vehicles, predictions, alerts) and GTFS.

## UI
The UI is being sketched on paper and will go into Figma. Nobody invents UI. Sketches/Figma in `design/` are the only source of truth.

## Team and agents
See `TEAM.md`. Agents: data-platform, insights-sponsors (Eren); game-engine (Tobi); client-bryan (Bryan); client-isabella (Isabella).
