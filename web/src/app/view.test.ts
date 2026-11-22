import { describe, expect, it } from 'vitest';
import type { MyRank, Spot, RankTier } from '../api/types';
import { MAP_CENTER, bigOffer, buildPlaces, ownerDots, pointsLine, projectPin, rankBarX, spotBadge } from './view';

const spot = (labels: Spot['labels'], demo = true): Spot => ({
  id: 's', name: 'Sample', category: { slug: 'cafe', display_name: 'Cafe' }, address: null, placement_type: 'listed', demo,
  sponsor_id: null, distance_m: null, fun_fact: null, labels, offers: [],
});
const lab = (slug: string, status: 'declared' | 'certified' = 'declared') => ({ slug, display_name: slug, status, evidence_url: null, declaration_note: 'x' });

describe('view helpers', () => {
  it('projects the stop to the design map centre and nearby places around it', () => {
    const stop = { lat: 42.35639, lon: -71.06236 };
    expect(projectPin(stop, stop)).toEqual(MAP_CENTER);
    const north = projectPin(stop, { lat: stop.lat + 0.001, lon: stop.lon });
    expect(north.y).toBeLessThan(MAP_CENTER.y);
  });

  it('keeps only pins inside the map and caps them at 7 places', () => {
    const stop = { id: 'p', name: 'Park Street', lat: 42.35639, lon: -71.06236, routes: [] };
    const items = Array.from({ length: 30 }, (_, i) => ({
      id: `i${i}`, title: `T${i}`, short_description: i % 2 ? 'a fact' : null, category: 'x', lat: stop.lat + 0.0005 * ((i % 5) - 2), lon: stop.lon + 0.0004 * (i - 15),
      distance_m: 1, source_id: 's', source_url: 'u', license: 'l', attribution: 'a', commercial_ok: true, needs_verify: false,
    }));
    const places = buildPlaces(stop, [{ id: 'f1', body: 'station fact' }], 'about Boston', items);
    expect(places.length).toBeLessThanOrEqual(7);
    expect(places[0].name).toBe('Park Street station');
    expect(places[0].facts[0].text).toBe('station fact');
    expect(places.every((p) => p.x >= 16 && p.x <= 332 && p.y >= 16 && p.y <= 300)).toBe(true);
  });

  it('shows LOCALLY OWNED only for declared or certified labels, never for pending or absent ones', () => {
    expect(spotBadge(spot([lab('local-independent')]))).toBe('LOCALLY OWNED');
    expect(spotBadge(spot([lab('local-independent', 'certified')]))).toBe('LOCALLY OWNED');
    expect(spotBadge(spot([]))).toBe('Demo');
    expect(spotBadge(spot([], false))).toBe('');
    // a pending label (should never arrive from the API) is not treated as verified
    expect(spotBadge(spot([{ ...lab('local-independent'), status: 'pending' as never }]))).toBe('Demo');
  });

  it('draws ownership dots only for labels the design defines', () => {
    expect(ownerDots(spot([lab('asian-owned'), lab('woman-owned')])).length).toBe(1);
    expect(ownerDots(spot([lab('latino-owned'), lab('woman-owned')])).length).toBe(2);
  });

  it('rank bar and points line', () => {
    const rank: MyRank = { rank: 2, name: 'Town Crier', avatar_key: 'x', discount_pct: 4, lifetime_points: 1000, next_rank: 3, next_rank_name: 'Lamplighter', next_rank_at: 1500, points_to_next: 500 };
    const tiers = [{ rank: 2, min_lifetime_points: 500 }] as RankTier[];
    expect(rankBarX(rank, tiers)).toBe(8 + 152);
    expect(pointsLine(rank)).toBe('1,000 pts · 500 to Lamplighter');
    expect(pointsLine({ ...rank, next_rank_name: null, points_to_next: null })).toBe('1,000 pts');
    expect(rankBarX({ ...rank, next_rank_at: null }, tiers)).toBe(312);
  });

  it('formats the big offer text', () => {
    expect(bigOffer({ kind: 'discount', discount_pct: 5, points_cost: null })).toBe('5% OFF');
    expect(bigOffer({ kind: 'free_item', discount_pct: null, points_cost: null })).toBe('FREE');
    expect(bigOffer({ kind: 'points_item', discount_pct: null, points_cost: 1000 })).toBe('1,000 PTS');
  });
});
