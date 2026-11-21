"""Tunable numbers. Proposals from contracts/api/game-engine.yaml x-rules."""

MAX_DISTANCE_M = 75
VEHICLE_SEEN_WITHIN_S = 300
VEHICLE_RADIUS_M = 300  # a live vehicle must be this close to the stop
COOLDOWN_PER_STOP_S = 1800

FIRST_VISIT_POINTS = 20
REPEAT_VISIT_POINTS = 2
REPEAT_VISITS_PER_STOP_PER_DAY = 1
DAILY_CHECKIN_POINTS_CAP = 100
COMPLETE_LINE_POINTS = 300
DELAY_COMPENSATION_POINTS = 50

# (rank, min lifetime points, discount percent, name, avatar key)
# 8 named ranks from Isabella's sketch (issue #42), low to high. Numbers are proposals.
RANKS = [
    (1, 0, 3, "Harbor Seal", "harbor-seal"),
    (2, 500, 4, "Town Crier", "town-crier"),
    (3, 1500, 5, "Lamplighter", "lamplighter"),
    (4, 4000, 7, "Midnight Rider", "midnight-rider"),
    (5, 8000, 8, "Tea Party Raider", "tea-party-raider"),
    (6, 15000, 10, "Children of Liberty", "children-of-liberty"),
    (7, 25000, 11, "Boston Lobstah", "boston-lobstah"),
    (8, 40000, 12, "Patriot", "patriot"),
]
REDEMPTIONS_PER_USER_PER_STORE_PER_WEEK = 1
MAX_DISCOUNT_VALUE_USD = 5
CODE_TTL_HOURS = 24
