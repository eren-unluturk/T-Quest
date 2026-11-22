// Ride verification: tap in at A, tap out at B, and the ride counts only if a real MBTA train made that trip.
// Prototype for issues #61 / #62. In the real app this belongs in game-engine, against Tiger Data vehicle history.
import { metres } from './geo';
import type { LatLon } from './geo';

export const ZONE_M = 75; // tap in only this close to the station
export const MAX_TRAIN_KMH = 80; // faster than any T train: a teleport, not a ride
const EARLY_MS = 20 * 60000; // tapped in up to 20 min before the train left
const LATE_MS = 2 * 60000; // or up to 2 min after
const ARRIVE_MS = 3 * 60000; // tapped out within 3 min of the train's arrival

export interface Station extends LatLon { id: string; name: string; lines: string[] }
export interface Trip { id: string; route: string | null; dep: number; arr: number }
export interface Check { ok: boolean; soft?: boolean; text: string }
export interface RideInput { from: Station; to: Station; t1: number; t2: number; trips: Trip[]; seenTrain: boolean }
export interface RideVerdict { ok: boolean; checks: Check[]; trip: Trip | null; kmh: number }

export const bostonTime = (t: number) =>
  new Date(t).toLocaleTimeString('en-GB', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false });

/** The MBTA schedule time window for a ride. The API's time filter does not wrap past midnight, so cap at 23:59. */
export function scheduleWindow(from: number, to: number) {
  const min = bostonTime(from - EARLY_MS);
  const late = bostonTime(to + 10 * 60000);
  return { min, max: late < min ? '23:59' : late };
}

interface SchedItem {
  attributes: { arrival_time: string | null; departure_time: string | null; stop_sequence: number };
  relationships: { stop: { data: { id: string } }; trip: { data: { id: string } }; route?: { data: { id: string } | null } };
}
interface StopItem { id: string; relationships?: { parent_station?: { data: { id: string } | null } } }
export interface SchedulesResponse { data?: SchedItem[]; included?: StopItem[] }

/** Trips that stop at station a and later at station b (any platform of either), sorted by departure. */
export function tripsFromSchedules(res: SchedulesResponse, a: string, b: string): Trip[] {
  const parent: Record<string, string> = {};
  for (const s of res.included ?? []) parent[s.id] = s.relationships?.parent_station?.data?.id ?? s.id;
  const trips: Record<string, { route: string | null; a?: SchedItem['attributes']; b?: SchedItem['attributes'] }> = {};
  for (const d of res.data ?? []) {
    const st = parent[d.relationships.stop.data.id] ?? d.relationships.stop.data.id;
    if (st !== a && st !== b) continue;
    const t = (trips[d.relationships.trip.data.id] ||= { route: d.relationships.route?.data?.id ?? null });
    t[st === a ? 'a' : 'b'] = d.attributes;
  }
  return Object.entries(trips)
    .filter(([, t]) => t.a && t.b && t.a.stop_sequence < t.b.stop_sequence)
    .map(([id, t]) => ({
      id, route: t.route,
      dep: Date.parse((t.a!.departure_time ?? t.a!.arrival_time)!),
      arr: Date.parse((t.b!.arrival_time ?? t.b!.departure_time)!),
    }))
    .filter((t) => Number.isFinite(t.dep) && Number.isFinite(t.arr))
    .sort((x, y) => x.dep - y.dep);
}

/** The scheduled trip this tap-in / tap-out pair rode, if any. */
export const matchTrip = (trips: Trip[], t1: number, t2: number) =>
  trips.find((t) => t1 <= t.dep + LATE_MS && t1 >= t.dep - EARLY_MS && Math.abs(t.arr - t2) <= ARRIVE_MS) ?? null;

export function verifyRide({ from, to, t1, t2, trips, seenTrain }: RideInput): RideVerdict {
  const dist = metres(from, to);
  const ms = Math.max(t2 - t1, 1);
  const kmh = dist / 1000 / (ms / 3600000);
  const mi = (dist / 1609.34).toFixed(1);
  const checks: Check[] = [{ ok: true, text: `Tapped in inside the ${ZONE_M} m zone at ${from.name}` }];
  const fast = kmh > MAX_TRAIN_KMH;
  checks.push({
    ok: !fast,
    text: fast ? `${mi} mi in ${Math.max(1, Math.round(ms / 1000))} s is faster than any train` : `${mi} mi in ${Math.round(ms / 60000)} min is a believable ride`,
  });
  const trip = fast ? null : matchTrip(trips, t1, t2);
  if (!fast) {
    checks.push({
      ok: !!trip,
      text: trip ? `Matches ${trip.route ? trip.route + ' ' : ''}trip ${trip.id}: left ${bostonTime(trip.dep)}, arrived ${bostonTime(trip.arr)}` : 'No real train made this trip at these times',
    });
  }
  checks.push({ ok: seenTrain, soft: true, text: seenTrain ? `A live train was near ${from.name} when you tapped in` : 'No live train seen at tap-in (soft signal)' });
  return { ok: !fast && !!trip, checks, trip, kmh };
}
