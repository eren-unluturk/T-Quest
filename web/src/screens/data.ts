import type { Api, NearbyParams } from '../api/client';
import type { Spot, Stop } from '../api/types';

/** There is no stop picker in the design, so Explore and Profile look at these demo stops (where the demo spots are). */
export const DEMO_STOPS = ['place-harsq', 'place-davis', 'place-fenwy', 'place-kencl'];
/** Home is the design's Park Street scene. */
export const HOME_STOP = 'place-pktrm';

export interface SpotAt { spot: Spot; stop: Stop }

export async function loadSpots(api: Api, params: NearbyParams = {}): Promise<{ spots: SpotAt[]; stops: Record<string, Stop> }> {
  const stops = await Promise.all(DEMO_STOPS.map((id) => api.stop(id)));
  const byId: Record<string, Stop> = Object.fromEntries(stops.map((s) => [s.id, s]));
  const results = await Promise.all(DEMO_STOPS.map((id) => api.nearby(id, { limit: 100, ...params }).then((n) => ({ id, n }))));
  const seen = new Set<string>();
  const spots: SpotAt[] = [];
  for (const { id, n } of results) {
    for (const spot of n.spots) {
      if (seen.has(spot.id)) continue; // a spot near two stops is listed once, at the first stop
      seen.add(spot.id);
      spots.push({ spot, stop: byId[id] });
    }
  }
  return { spots, stops: byId };
}
