#!/usr/bin/env node
// Create the kickoff seed issues. Idempotent by title (skips if an open issue with same title exists).
// Usage: node scripts/seed-issues.mjs [--dry]
import { gh, parseArgs } from './lib.mjs';

const dry = parseArgs(process.argv.slice(2)).dry;
const S = (from, to, type, title, body, files = '_No response_') => ({ from, to, type, title, body, files });

const seeds = [
  S('data-platform', 'all', 'request', 'Publish v0 Tiger Data schema + docker-compose/env instructions',
    'Publish v0 schema in contracts/db/: stops, routes, users, consent, rider_events (hypertable), points_ledger, rewards, sponsors, offers, badges, physical_rewards, redemptions, store_inventory, user_collections. Include docker-compose and .env instructions so everyone can run it locally and against Tiger Cloud. Consumers: please list missing columns by issue to:data-platform.', 'contracts/db/, data-platform/docker-compose.yml, .env.example'),
  S('data-platform', 'game-engine', 'handoff', 'MBTA ingestion plan and realtime tables/aggregates (to game-engine, insights-sponsors)',
    'Plan: MBTA V3 static + GTFS loaded into stops/routes; realtime vehicles, predictions, alerts ingested into compressed hypertables with retention. Planned aggregates: home-line detection, leaderboard, personal stats. Please confirm which columns and refresh cadences you need. (Also addressed to insights-sponsors: see to:insights-sponsors cross-post below.)', 'contracts/db/'),
  S('data-platform', 'insights-sponsors', 'handoff', 'MBTA ingestion plan and realtime tables/aggregates (to insights-sponsors)',
    'Same plan as the game-engine copy: realtime hypertables plus home-line detection and leaderboard continuous aggregates. Tell us what the recommendation and analytics queries need from rider_events/time_bucket aggregates.', 'contracts/db/'),
  S('game-engine', 'data-platform', 'request', 'Ledger / rank / leaderboard table requirements, check-in event shape, redemption and badge-unlock tables',
    'Need: append-only points_ledger, rank/tier tables, leaderboard aggregate, check-in event shape for rider_events, redemptions (issued/claimed/expired, single-use code, store id), badge-unlock tables. I will propose the check-in event JSON Schema in contracts/events/ via a contract-change issue.', 'contracts/db/, contracts/events/'),
  S('game-engine', 'insights-sponsors', 'request', 'Reward/offer redemption contract, rank-tier discount rules, physical-reward redemption + store verification',
    'Need to agree: reward/offer redemption contract; rank-tier discount rules (rank 1 ~5%, rising, top ranks free items); physical-reward (sticker/patch) redemption and store-verification contract (single-use code/QR, per-store inventory, per-user limits, rank/achievement requirements).', 'contracts/api/'),
  S('insights-sponsors', 'data-platform', 'request', 'Stop metadata fields, consent table, store partner and physical-reward catalog fields',
    'Need: stop metadata fields for facts and Freedom Trail content; consent table requirements (purpose, granted_at, revoked_at, scope); store partner and physical-reward catalog fields (store, item type sticker/patch/other, badge link, stock, limits).', 'contracts/db/'),
  S('insights-sponsors', 'game-engine', 'request', 'Sponsored-quest data model and achievement-to-patch/sticker mapping',
    'Propose sponsored-quest data model and which achievements map to which patches/stickers (e.g. line completion patch, Freedom Trail sticker, rank patch). Please confirm unlock rules from your side.', 'contracts/api/'),
  S('client-bryan', 'all', 'request', 'Need OpenAPI contracts from each service by target time; auth/session assumptions',
    'Please publish OpenAPI in contracts/api/ for each service as early as possible (target: set a time in replies). Assumptions to confirm: a user id issued by game-engine/data-platform session, bearer token on requests, location sent only with explicit consent. No UI is assumed.', 'contracts/api/'),
  S('client-isabella', 'humans', 'question', 'Sketches/Figma not available yet',
    'Bryan and Isabella: please drop sketch photos in design/sketches/ and Figma links in design/FIGMA_LINKS.md. Client agents will not build UI until these exist.', 'design/'),
  S('client-bryan', 'client-isabella', 'question', 'Agree and confirm the client work split',
    'Default split: Bryan = app foundation (shell, navigation from sketches, generated API client, state/data layer, auth/session, location/map plumbing); Isabella = screens and visual implementation from Figma (tokens, components, screens). Reply to confirm or propose changes.', 'client-bryan/PLAN.md, client-isabella/PLAN.md'),
  S('humans', 'all', 'request', 'Kickoff: pull, fill TEAM.md, run setup-me',
    'Everyone: git pull, fill in your GitHub handle in TEAM.md and team.json, then run `node scripts/setup-me.mjs <person>`. See docs/ONBOARDING.md.', 'docs/ONBOARDING.md'),
];

for (const s of seeds) {
  const text = [
    '### From', '', s.from, '', '### To', '', s.to, '', '### Type', '', s.type, '',
    '### Summary', '', s.title, '', '### What I need', '', s.body, '',
    '### Contract/files involved', '', s.files, '', '### Needed by', '', '_No response_', '', `[${s.from}]`,
  ].join('\n');
  const labels = [`to:${s.to}`, `from:${s.from}`, `type:${s.type}`];
  const args = ['issue', 'create', '--title', `[${s.from}] ${s.title}`, '--body', text];
  for (const l of labels) args.push('--label', l);
  if (dry) { console.log(`gh ${args.map((a) => JSON.stringify(a)).join(' ')}`); continue; }
  console.log(gh(args).trim());
}
