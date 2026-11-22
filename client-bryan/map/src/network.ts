// The subway as a graph, and T directions over it.
// Built from MBTA /route_patterns (typical patterns, ordered stops of a representative trip, platforms folded into parent stations).

export interface Edge { to: string; route: string; toward: string }
export type Network = Record<string, Edge[]>;
export interface Leg { route: string; from: string; to: string; stops: number; toward: string }
export interface TRoute { legs: Leg[]; minutes: number }

export const STOP_MIN = 2;
export const TRANSFER_MIN = 5;

interface JsonApiRef { type: string; id: string }
interface JsonApiItem {
  type: string; id: string;
  attributes?: { typicality?: number; [k: string]: unknown };
  relationships?: Record<string, { data: JsonApiRef | JsonApiRef[] | null }>;
}
export interface RoutePatternsResponse { data?: JsonApiItem[]; included?: JsonApiItem[] }

const one = (r: { data: JsonApiRef | JsonApiRef[] | null } | undefined) => (r && r.data && !Array.isArray(r.data) ? r.data : null);
const many = (r: { data: JsonApiRef | JsonApiRef[] | null } | undefined) => (r && Array.isArray(r.data) ? r.data : []);

/** Links consecutive stops of every typical pattern in both directions. `name` labels the terminus for "toward". */
export function buildNetwork(res: RoutePatternsResponse, name: (stationId: string) => string): Network {
  const inc: Record<string, JsonApiItem> = {};
  for (const x of res.included ?? []) inc[x.type + x.id] = x;
  const adj: Network = {};
  const link = (a: string, b: string, route: string, toward: string) => (adj[a] ||= []).push({ to: b, route, toward });
  for (const pat of res.data ?? []) {
    if (pat.attributes?.typicality !== 1) continue;
    const tripRef = one(pat.relationships?.representative_trip);
    const route = one(pat.relationships?.route)?.id;
    const trip = tripRef && inc['trip' + tripRef.id];
    if (!trip || !route) continue;
    const ids = many(trip.relationships?.stops).map((d) => one(inc['stop' + d.id]?.relationships?.parent_station)?.id ?? d.id);
    if (ids.length < 2) continue;
    for (let i = 1; i < ids.length; i++) {
      link(ids[i - 1], ids[i], route, name(ids[ids.length - 1]));
      link(ids[i], ids[i - 1], route, name(ids[0]));
    }
  }
  return adj;
}

/** Fewest minutes from station a to b: STOP_MIN a stop, plus TRANSFER_MIN to change trains. Null when unreachable. */
export function tRoute(net: Network, a: string, b: string): TRoute | null {
  if (a === b) return { legs: [], minutes: 0 };
  type Step = { from: string; st: string; to: string; route: string; toward: string };
  const dist: Record<string, number> = { [a + '|']: 0 };
  const prev: Record<string, Step> = {};
  const done = new Set<string>();
  const queue: [number, string, string][] = [[0, a, '']];
  while (queue.length) {
    queue.sort((x, y) => x[0] - y[0]);
    const [d, st, route] = queue.shift()!;
    const key = st + '|' + route;
    if (done.has(key)) continue;
    done.add(key);
    if (st === b) {
      const steps: Step[] = [];
      for (let k = key; prev[k]; k = prev[k].from) steps.unshift(prev[k]);
      const legs: Leg[] = [];
      for (const e of steps) {
        const last = legs[legs.length - 1];
        if (last && last.route === e.route) { last.to = e.to; last.stops++; last.toward = e.toward; }
        else legs.push({ route: e.route, from: e.st, to: e.to, stops: 1, toward: e.toward });
      }
      return { legs, minutes: d };
    }
    for (const e of net[st] ?? []) {
      const nd = d + STOP_MIN + (route && route !== e.route ? TRANSFER_MIN : 0);
      const nk = e.to + '|' + e.route;
      if (nd < (dist[nk] ?? Infinity)) {
        dist[nk] = nd;
        prev[nk] = { from: key, st, to: e.to, route: e.route, toward: e.toward };
        queue.push([nd, e.to, e.route]);
      }
    }
  }
  return null;
}

const servedBy = (net: Network, id: string) => new Set((net[id] ?? []).map((e) => e.route));

/** "Red Line", "Mattapan Trolley", "Green Line B branch", or "Green Line (any branch)" when several branches serve both ends. */
export function routeName(net: Network, route: string, leg?: Pick<Leg, 'from' | 'to'>): string {
  if (route === 'Mattapan') return 'Mattapan Trolley';
  if (!route.startsWith('Green-')) return `${route} Line`;
  const shared = leg && [...servedBy(net, leg.from)].filter((x) => x.startsWith('Green-') && servedBy(net, leg.to).has(x)).length > 1;
  return shared ? 'Green Line (any branch)' : `Green Line ${route.slice(6)} branch`;
}
