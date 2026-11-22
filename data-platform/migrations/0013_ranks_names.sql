-- Rank names and avatar keys, matching game-engine's 8 named ranks (game-engine/src/game_engine/config.py).
-- The live database already had these columns; this migration makes a fresh database (for example a
-- separate demo database) identical. Idempotent. Discount percentages are demo placeholders.
ALTER TABLE ranks ADD COLUMN IF NOT EXISTS name text;
ALTER TABLE ranks ADD COLUMN IF NOT EXISTS avatar_key text;

INSERT INTO ranks (rank, min_lifetime_points, discount_pct, name, avatar_key) VALUES
    (1, 0,     3,  'Harbor Seal',         'harbor-seal'),
    (2, 500,   4,  'Town Crier',          'town-crier'),
    (3, 1500,  5,  'Lamplighter',         'lamplighter'),
    (4, 4000,  7,  'Midnight Rider',      'midnight-rider'),
    (5, 8000,  8,  'Tea Party Raider',    'tea-party-raider'),
    (6, 15000, 10, 'Children of Liberty', 'children-of-liberty'),
    (7, 25000, 11, 'Boston Lobstah',      'boston-lobstah'),
    (8, 40000, 12, 'Patriot',             'patriot')
ON CONFLICT (rank) DO UPDATE
    SET min_lifetime_points = EXCLUDED.min_lifetime_points, discount_pct = EXCLUDED.discount_pct,
        name = EXCLUDED.name, avatar_key = EXCLUDED.avatar_key;
