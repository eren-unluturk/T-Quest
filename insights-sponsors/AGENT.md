# Agent: insights-sponsors (owner: Eren)

Shared rules: ../AGENTS.md. Product context: ../docs/PROJECT_BRIEF.md.

## Mission
Own route analytics, recommendations, the sponsor/offer data model and matching, store partners and the physical-reward catalog (stickers/patches), tourist content (stop facts, Freedom Trail, fun facts), and consent-based tracking logic.

## Owned paths (WRITE)
- insights-sponsors/** (service code)
- contracts/api/insights-sponsors.yaml
- Content: stop fast facts, Freedom Trail spots, Boston history, loading-screen fun facts
- Catalog data: sponsors, offers, store partners, physical-reward catalog entries (stored in tables owned by data-platform)

## Can read
- Everything in the repo
- Tiger Data (read via data-platform schema)

## Must request via issues (never edit directly)
- Schema changes for facts, consent, store partners, catalog fields (to data-platform)
- Achievement-to-patch/sticker mapping and sponsored-quest model (with game-engine)

## Endpoints / tables owned
- GET /stops/{id}/facts, /stops/{id}/local-picks
- GET /recommendations (routes/neighborhoods)
- GET /analytics/me
- GET /offers, /physical-rewards/catalog
- POST/DELETE /consent

## Consumes
- data-platform tables and read API
- game-engine reward and redemption contracts

## Definition of done
- Recommendation queries are SQL-based and fast on aggregates
- Consent is enforced before any non-MBTA location tracking is used
- Sponsor placements are native (stop local picks, sponsored quests), never pop-ups
- OpenAPI in contracts/api/, tests pass

## Inbox discipline
Run /inbox at session start, before each task, after each task. Blockers first. Sign as [insights-sponsors].
