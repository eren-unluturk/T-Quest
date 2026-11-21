---
id: 003
title: Rewards schema - sponsors, stores, offers, rewards, quests, badges, physical rewards, redemptions
status: ready
issue: 6
depends_on: [002]
---
## Goal
Migration for the sponsor, reward, badge and redemption tables requested in #4 (game-engine) and #6 (insights-sponsors), matching game-engine's in-memory redemption rules.

## Context
- `../docs/PROJECT_BRIEF.md` sections Sponsors and Physical rewards
- `../game-engine/src/game_engine/redemption.py` (code alphabet, 10-char codes, statuses issued/claimed/expired, store-scoped verify, per-offer stock, weekly per-user-per-store limit, 24h TTL)
- `../contracts/api/game-engine.yaml` (Quest, Collection, Redemption schemas; X-Store-Key header for store verify)
- `migrations/0001_core.sql` from 002

## Steps
Create `migrations/0002_rewards.sql` (idempotent):
1. `sponsors`: `id uuid pk`, `name not null`, `category text check in ('food','clothing','sports','retail','other')`, `website`, `logo_url`, `active boolean default true`, `created_at`.
2. `stores` (partner store locations): `id uuid pk`, `sponsor_id fk`, `name`, `address`, `lat`, `lon`, `nearest_stop_id text fk stops null`, `store_key_hash text null` (hash of the X-Store-Key; never store the raw key), `active boolean default true`. Index on `nearest_stop_id`.
3. `offers` (native placements and rank discounts): `id uuid pk`, `sponsor_id fk`, `store_id fk null` (null = all stores of sponsor), `title`, `description`, `kind text check in ('discount','free_item','local_pick')`, `min_rank int default 1`, `points_cost int default 0`, `discount_pct int null`, `max_value_usd numeric(6,2) null`, `stock int null` (null = unlimited), `starts_at`, `ends_at`, `active`.
4. `rewards` (points-redeemable catalog, e.g. Red Sox hat, ticket discount): `id uuid pk`, `sponsor_id fk null`, `title`, `description`, `kind text check in ('merch','ticket','digital','other')`, `points_cost int not null`, `min_rank int default 1`, `stock int null`, `active`.
5. `badges`: `id text pk` (slug, e.g. `line-red-complete`, `freedom-trail`, `rank-3`), `name`, `description`, `kind text check in ('line_complete','rank','trail','stop_count','event','sponsor')`, `criteria jsonb default '{}'`, `image_url`.
6. `quests`: `id uuid pk`, `title`, `goal text`, `criteria jsonb`, `sponsor_id fk null`, `reward_points int default 0`, `reward_badge_id text fk badges null`, `starts_at`, `ends_at`, `active`.
7. `physical_rewards` (#6 catalog): `id uuid pk`, `sponsor_id fk null`, `name`, `item_type text check in ('sticker','patch','pin','other')`, `badge_id text fk badges not null` (each physical reward maps to a badge), `min_rank int default 1`, `per_user_limit int default 1`, `image_url`, `active`.
8. `store_inventory`: `store_id fk`, `physical_reward_id fk`, `stock int not null check (stock >= 0)`, `updated_at`, pk `(store_id, physical_reward_id)`.
9. `user_collections` (badge unlocks / the bag): `user_id fk`, `badge_id fk`, `earned_at timestamptz default now()`, `source text` (e.g. `checkin`, `quest`, `rank`), `source_ref text null`, pk `(user_id, badge_id)`.
10. `redemptions`: `id uuid pk`, `code text unique not null check (code ~ '^[A-HJ-NP-Z2-9]{10}$')`, `user_id fk`, `store_id fk null`, `offer_id fk null`, `reward_id fk null`, `physical_reward_id fk null`, check exactly one of offer_id/reward_id/physical_reward_id is not null, `status text check in ('issued','claimed','expired') default 'issued'`, `points_spent int default 0`, `issued_at default now()`, `expires_at not null`, `claimed_at null`, `claimed_store_id fk null`. Indexes: `(user_id, store_id, issued_at desc)` (weekly limit), `(status, expires_at)`.
11. A SQL function `expire_redemptions()` that sets `status='expired'` where `status='issued' and expires_at < now()`, returning the count. Do not schedule it (game-engine may call it or we add a job later).
12. Extend `seeds/dev_seed.sql` with 1 sponsor, 1 store, 1 offer, 2 badges, 1 physical reward with inventory.

## Acceptance criteria
- Migration applies on top of 0001; re-run is a no-op.
- Redemption check constraint rejects rows with zero or two target ids; code regex rejects `0`, `O`, `1`, `I`.
- `store_inventory.stock` cannot go negative.
- A physical reward cannot exist without a badge.
- `expire_redemptions()` expires only past-due issued rows.

## Tests to run
`pytest -q` with compose DB up. Add `tests/test_rewards_schema.py` covering every acceptance criterion.

## Out of scope
Business logic for issuing/verifying codes (game-engine owns it). API endpoints. Editing `../contracts/`.

Commits and PR/issue text must contain no Co-Authored-By or any agent attribution.
