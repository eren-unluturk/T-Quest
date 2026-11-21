"""Placeholder rank table mirroring game-engine's 8 named ranks (the shared `ranks` table is the source
of truth in Postgres mode). Discount percentages are demo placeholders."""
RANKS = [
    {"rank": 1, "name": "Harbor Seal", "avatar_key": "harbor-seal", "min_lifetime_points": 0, "discount_pct": 3},
    {"rank": 2, "name": "Town Crier", "avatar_key": "town-crier", "min_lifetime_points": 500, "discount_pct": 4},
    {"rank": 3, "name": "Lamplighter", "avatar_key": "lamplighter", "min_lifetime_points": 1500, "discount_pct": 5},
    {"rank": 4, "name": "Midnight Rider", "avatar_key": "midnight-rider", "min_lifetime_points": 4000, "discount_pct": 7},
    {"rank": 5, "name": "Tea Party Raider", "avatar_key": "tea-party-raider", "min_lifetime_points": 8000, "discount_pct": 8},
    {"rank": 6, "name": "Children of Liberty", "avatar_key": "children-of-liberty", "min_lifetime_points": 15000, "discount_pct": 10},
    {"rank": 7, "name": "Boston Lobstah", "avatar_key": "boston-lobstah", "min_lifetime_points": 25000, "discount_pct": 11},
    {"rank": 8, "name": "Patriot", "avatar_key": "patriot", "min_lifetime_points": 40000, "discount_pct": 12},
]
TOP_RANK = 8
