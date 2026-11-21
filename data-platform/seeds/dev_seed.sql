-- Dev seed (not a migration). Applied by: python -m data_platform.seed
INSERT INTO routes (id, short_name, long_name, mode, route_type, color, text_color, line_id, sort_order) VALUES
    ('Red',     NULL, 'Red Line',   'subway',     1, 'DA291C', 'FFFFFF', 'line-Red',   1),
    ('Green-B', 'B',  'Green Line B', 'light_rail', 0, '00843D', 'FFFFFF', 'line-Green', 2),
    ('1',       '1',  'Harvard Square - Nubian Station', 'bus', 3, 'FFC72C', '000000', 'line-1', 3)
ON CONFLICT DO NOTHING;

INSERT INTO stops (id, name, lat, lon, municipality, is_freedom_trail, neighborhood) VALUES
    ('place-pktrm', 'Park Street',      42.356395, -71.062424, 'Boston',    true,  'Downtown'),
    ('place-dwnxg', 'Downtown Crossing', 42.355518, -71.060225, 'Boston',    false, 'Downtown'),
    ('place-sstat', 'South Station',    42.352271, -71.055242, 'Boston',    false, 'Financial District'),
    ('place-harsq', 'Harvard',          42.373362, -71.118956, 'Cambridge', false, 'Harvard Square'),
    ('place-bland', 'Blandford Street', 42.349293, -71.100258, 'Boston',    false, 'Kenmore')
ON CONFLICT DO NOTHING;

INSERT INTO users (id, username, display_name) VALUES
    ('00000000-0000-0000-0000-000000000001', 'alice', 'Alice'),
    ('00000000-0000-0000-0000-000000000002', 'bob',   'Bob')
ON CONFLICT DO NOTHING;

-- Rewards seed
INSERT INTO sponsors (id, name, category, website) VALUES
    ('10000000-0000-0000-0000-000000000001', 'Demo Coffee Co', 'food', 'https://example.com')
ON CONFLICT DO NOTHING;

INSERT INTO stores (id, sponsor_id, name, address, lat, lon, nearest_stop_id) VALUES
    ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'Demo Coffee - Park St', '1 Park St, Boston, MA', 42.3566, -71.0620, 'place-pktrm')
ON CONFLICT DO NOTHING;

INSERT INTO offers (id, sponsor_id, store_id, title, description, kind, min_rank, discount_pct) VALUES
    ('30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     '20000000-0000-0000-0000-000000000001', 'Local pick: house latte',
     'Native placement near Park Street', 'local_pick', 1, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO badges (id, name, description, kind) VALUES
    ('freedom-trail', 'Freedom Trail', 'Visit the Freedom Trail stops', 'trail'),
    ('rank-3', 'Rank 3', 'Reach rank 3', 'rank')
ON CONFLICT DO NOTHING;

INSERT INTO physical_rewards (id, sponsor_id, name, item_type, badge_id, min_rank, per_user_limit) VALUES
    ('40000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
     'Freedom Trail sticker', 'sticker', 'freedom-trail', 1, 1)
ON CONFLICT DO NOTHING;

INSERT INTO store_inventory (store_id, physical_reward_id, stock) VALUES
    ('20000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', 50)
ON CONFLICT DO NOTHING;
