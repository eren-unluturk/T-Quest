import { describe, expect, it } from 'vitest';
import { decodePolyline, metres, nearest } from './geo';
import { buildNetwork, routeName, tRoute } from './network';
import type { RoutePatternsResponse } from './network';
import { lineOf } from './theme';
import { segment } from './track';
import type { Shapes } from './track';
import { matchTrip, scheduleWindow, tripsFromSchedules, verifyRide } from './verify';
import type { SchedulesResponse, Station } from './verify';

// A tiny subway: Red A-B-C, Orange B-D, Green-B and Green-C share E-F, then split to G (B) and H (C).
function pattern(id: string, route: string, stops: string[]) {
  return {
    data: { type: 'route_pattern', id, attributes: { typicality: 1 }, relationships: { route: { data: { type: 'route', id: route } }, representative_trip: { data: { type: 'trip', id: 't' + id } } } },
    trip: { type: 'trip', id: 't' + id, relationships: { stops: { data: stops.map((s) => ({ type: 'stop', id: s + '-plat' })) } } },
    stops: stops.map((s) => ({ type: 'stop', id: s + '-plat', relationships: { parent_station: { data: { type: 'stop', id: s } } } })),
  };
}
const pats = [pattern('r', 'Red', ['A', 'B', 'C']), pattern('o', 'Orange', ['B', 'D']), pattern('gb', 'Green-B', ['E', 'F', 'G']), pattern('gc', 'Green-C', ['E', 'F', 'H'])];
const res: RoutePatternsResponse = {
  data: [...pats.map((p) => p.data), { type: 'route_pattern', id: 'odd', attributes: { typicality: 3 }, relationships: {} }],
  included: pats.flatMap((p) => [p.trip, ...p.stops]),
};
const net = buildNetwork(res, (id) => `Station ${id}`);

describe('T directions', () => {
  it('links platforms as parent stations in both directions, skipping atypical patterns', () => {
    expect(net.A.map((e) => e.to)).toEqual(['B']);
    expect(net.B.map((e) => `${e.route}:${e.to}`).sort()).toEqual(['Orange:D', 'Red:A', 'Red:C']);
    expect(net.C[0].toward).toBe('Station A');
  });
  it('finds a one-seat ride: 2 min a stop', () => {
    expect(tRoute(net, 'A', 'C')).toEqual({ minutes: 4, legs: [{ route: 'Red', from: 'A', to: 'C', stops: 2, toward: 'Station C' }] });
  });
  it('adds 5 min for a change and reports where', () => {
    const r = tRoute(net, 'A', 'D')!;
    expect(r.minutes).toBe(2 + 2 + 5);
    expect(r.legs.map((l) => `${l.route} ${l.from}->${l.to}`)).toEqual(['Red A->B', 'Orange B->D']);
  });
  it('returns an empty trip for the same station and null when unreachable', () => {
    expect(tRoute(net, 'A', 'A')).toEqual({ legs: [], minutes: 0 });
    expect(tRoute(net, 'A', 'G')).toBeNull();
  });
  it('names a Green branch only when the leg needs it', () => {
    expect(routeName(net, 'Green-B', { from: 'E', to: 'F' })).toBe('Green Line (any branch)');
    expect(routeName(net, 'Green-B', { from: 'E', to: 'G' })).toBe('Green Line B branch');
    expect(routeName(net, 'Red')).toBe('Red Line');
    expect(routeName(net, 'Mattapan')).toBe('Mattapan Trolley');
  });
});

describe('ride verification', () => {
  const park: Station = { id: 'place-pktrm', name: 'Park Street', lat: 42.35639, lon: -71.0624, lines: ['Red', 'Green'] };
  const harvard: Station = { id: 'place-harsq', name: 'Harvard', lat: 42.373362, lon: -71.118956, lines: ['Red'] };
  const dep = Date.parse('2026-11-22T15:00:00-05:00');
  const arr = dep + 11 * 60000;
  const sched = (trip: string, stop: string, seq: number, t: number) => ({
    attributes: { arrival_time: new Date(t).toISOString(), departure_time: new Date(t).toISOString(), stop_sequence: seq },
    relationships: { stop: { data: { id: stop } }, trip: { data: { id: trip } }, route: { data: { id: 'Red' } } },
  });
  const schedules: SchedulesResponse = {
    data: [sched('T1', '70075', 10, dep), sched('T1', '70068', 17, arr), sched('T2', '70068', 3, dep), sched('T2', '70075', 9, arr)],
    included: [{ id: '70075', relationships: { parent_station: { data: { id: 'place-pktrm' } } } }, { id: '70068', relationships: { parent_station: { data: { id: 'place-harsq' } } } }],
  };
  const trips = tripsFromSchedules(schedules, park.id, harvard.id);

  it('keeps only trips that stop at A before B', () => {
    expect(trips.map((t) => t.id)).toEqual(['T1']);
    expect(trips[0]).toMatchObject({ route: 'Red', dep, arr });
  });
  it('accepts a tap-out at the real arrival', () => {
    const v = verifyRide({ from: park, to: harvard, t1: dep - 5 * 60000, t2: arr + 60000, trips, seenTrain: true });
    expect(v.ok).toBe(true);
    expect(v.trip?.id).toBe('T1');
    expect(v.checks.every((c) => c.ok)).toBe(true);
  });
  it('rejects a teleport (tap out right after tapping in)', () => {
    const v = verifyRide({ from: park, to: harvard, t1: dep, t2: dep + 20000, trips, seenTrain: true });
    expect(v.ok).toBe(false);
    expect(v.kmh).toBeGreaterThan(80);
    expect(v.checks[1]).toMatchObject({ ok: false });
  });
  it('rejects a believable speed that no train matches', () => {
    const v = verifyRide({ from: park, to: harvard, t1: dep + 30 * 60000, t2: dep + 45 * 60000, trips, seenTrain: false });
    expect(v.ok).toBe(false);
    expect(v.checks.find((c) => c.text.includes('No real train'))).toBeTruthy();
  });
  it('matches within the windows: up to 20 min early, 2 min late, 3 min from arrival', () => {
    expect(matchTrip(trips, dep - 20 * 60000, arr)).not.toBeNull();
    expect(matchTrip(trips, dep - 21 * 60000, arr)).toBeNull();
    expect(matchTrip(trips, dep + 2 * 60000, arr)).not.toBeNull();
    expect(matchTrip(trips, dep + 3 * 60000, arr)).toBeNull();
    expect(matchTrip(trips, dep, arr + 4 * 60000)).toBeNull();
  });
  it('caps the schedule window at 23:59 instead of wrapping past midnight', () => {
    const lateNight = Date.parse('2026-11-22T23:55:00-05:00');
    expect(scheduleWindow(lateNight, lateNight)).toEqual({ min: '23:35', max: '23:59' });
  });
});

describe('geometry', () => {
  it('measures Park Street to Harvard at about 5 km', () => {
    const d = metres({ lat: 42.35639, lon: -71.0624 }, { lat: 42.373362, lon: -71.118956 });
    expect(d).toBeGreaterThan(4900);
    expect(d).toBeLessThan(5100);
  });
  it('decodes an encoded polyline', () => {
    expect(decodePolyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@')).toEqual([[-120.2, 38.5], [-120.95, 40.7], [-126.453, 43.252]]);
  });
  it('finds the nearest station', () => {
    expect(nearest([{ id: 'a', lat: 0, lon: 0 }, { id: 'b', lat: 1, lon: 1 }], { lat: 0.9, lon: 0.9 })?.id).toBe('b');
  });
  it('cuts the track between two stations and measures it', () => {
    const shapes: Shapes = { type: 'FeatureCollection', features: [{ type: 'Feature', properties: { color: '#DA291C', line: 'Red', route: 'Red' },
      geometry: { type: 'LineString', coordinates: [[-71.0, 42.30], [-71.0, 42.31], [-71.0, 42.32], [-71.0, 42.33]] } }] };
    const s = segment(shapes, 'Red', { lat: 42.31, lon: -71.0 }, { lat: 42.33, lon: -71.0 })!;
    expect(s.coords).toHaveLength(3);
    expect(s.miles).toBeCloseTo(1.38, 1);
    expect(segment(shapes, 'Orange', { lat: 42.31, lon: -71.0 }, { lat: 42.33, lon: -71.0 })).toBeNull();
    expect(segment(shapes, 'Red', { lat: 42.4, lon: -71.0 }, { lat: 42.33, lon: -71.0 })).toBeNull();
  });
  it('counts the Mattapan Trolley as Red and every Green branch as Green', () => {
    expect(['Mattapan', 'Green-D', 'Orange'].map(lineOf)).toEqual(['Red', 'Green', 'Orange']);
  });
});
