# game-engine

Owner: Tobi. Python 3.11+ FastAPI service (see DECISIONS.md).

Own game logic: check-in verification (proximity + live-vehicle sanity check), points ledger logic, ranks/tiers, quests/collectibles, badge/achievement unlock rules (which achievements unlock which patches/stickers), friends/leaderboards, delay compensation, reward and physical-reward redemption (code generation, single-use, store verification endpoint), and bus parity.

See AGENT.md for charter, owned paths and definition of done.

- `src/` - service code
- `tests/` - tests
