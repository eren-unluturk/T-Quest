// Pure helpers that turn API data into the values the ported design markup expects.
import type { ContentItem, MyRank, RankTier, Spot, Stop } from '../api/types';

/** Design tokens (design/tokens/colors.json). */
export const COLORS = {
  navy: '#1D3557', yellow: '#FFC93C', pink: '#F4A6C6', lightBlue: '#A8DADC', lightGreen: '#B8E0A8', orange: '#F4A261',
  steelBlue: '#457B9D', red: '#E63946', cream: '#FFF8EC', honey: '#FFE3A3',
};
export const PALETTE = [COLORS.yellow, COLORS.pink, COLORS.lightBlue, COLORS.lightGreen, COLORS.orange, COLORS.honey];
/** Ownership dots from the design tokens. Only labels the design defines get a dot. */
export const OWNER_DOT: Record<string, string> = { 'latino-owned': '#E63946', 'woman-owned': '#F4A6C6', 'african-american-owned': '#457B9D' };
/** The design's "Owned by" options mapped to API label slugs. */
export const OWNER_OPTIONS: { key: string; label: string; slug: string; dot: string }[] = [
  { key: 'local', label: 'Locally owned', slug: 'local-independent', dot: '#FFFFFF' },
  { key: 'latinx', label: 'Latinx-owned', slug: 'latino-owned', dot: OWNER_DOT['latino-owned'] },
  { key: 'women', label: 'Women-owned', slug: 'woman-owned', dot: OWNER_DOT['woman-owned'] },
  { key: 'black', label: 'Black-owned', slug: 'african-american-owned', dot: OWNER_DOT['african-american-owned'] },
];
/** The design's category bubbles mapped to API category slugs (Sightseeing has no spot category). */
export const CATEGORY_MAP: Record<string, string[]> = {
  All: [], Sightseeing: [], Restaurants: ['restaurant'], Drinks: ['bar'], 'Cafés': ['cafe'], Shopping: ['store', 'clothing', 'grocery'],
};
export const CATEGORY_ICON: Record<string, string> = {
  restaurant: 'M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10M17 3c-2 2-2 6 0 8v10',
  bar: 'M7 8h10l-1 13H8zM12 8l2-5h3',
  cafe: 'M4 9h12v6a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5zM16 11h2a2 2 0 0 1 0 4h-2M8 3v3M12 3v3',
  store: 'M5 8h14l-1 13H6zM9 8V6a3 3 0 0 1 6 0v2',
  clothing: 'M5 8h14l-1 13H6zM9 8V6a3 3 0 0 1 6 0v2',
  grocery: 'M5 8h14l-1 13H6zM9 8V6a3 3 0 0 1 6 0v2',
  other: 'M3 21h18M5 18h14M6 10v8M10 10v8M14 10v8M18 10v8M3 10l9-6 9 6z',
};

/** Home map: pixels per degree, taken from two places the design pins (State House and Park Street station). */
const PX_PER_DEG_LON = 40741;
const PX_PER_DEG_LAT = 32773;
export const MAP_CENTER = { x: 250, y: 140 }; // where the design puts Park Street station

export function projectPin(stop: { lat: number; lon: number }, p: { lat: number; lon: number }) {
  return { x: MAP_CENTER.x + (p.lon - stop.lon) * PX_PER_DEG_LON, y: MAP_CENTER.y - (p.lat - stop.lat) * PX_PER_DEG_LAT };
}
export const inMap = (x: number, y: number) => x >= 16 && x <= 332 && y >= 16 && y <= 300;

export interface Place { id: string; name: string; x: number; y: number; c: string; facts: { id: string; text: string }[]; nearby?: string; source?: string; attribution?: string }

export function buildPlaces(stop: Stop, stopFacts: { id: string; body: string }[], fallbackText: string | undefined, items: ContentItem[]): Place[] {
  const places: Place[] = [{
    id: `stop:${stop.id}`, name: `${stop.name} station`, ...MAP_CENTER, c: COLORS.red,
    facts: stopFacts.map((f) => ({ id: f.id, text: f.body })), nearby: fallbackText,
  }];
  let n = 0;
  for (const it of items) {
    if (it.lat == null || it.lon == null) continue;
    const { x, y } = projectPin(stop, { lat: it.lat, lon: it.lon });
    if (!inMap(x, y) || places.some((p) => Math.hypot(p.x - x, p.y - y) < 18)) continue;
    places.push({
      id: it.id, name: it.title, x, y, c: PALETTE[n++ % PALETTE.length],
      facts: it.short_description ? [{ id: it.id, text: it.short_description }] : [], nearby: fallbackText,
      source: it.source_url, attribution: it.attribution,
    });
    if (places.length >= 7) break;
  }
  return places;
}

export const fmtInt = (n: number) => Math.round(n).toLocaleString('en-US');
export const fmtMiles = (n: number) => (Math.round(n * 10) / 10).toString();

/** x position (8..312) of the yellow marker on the rank bar. */
export function rankBarX(rank: MyRank, tiers: RankTier[]): number {
  const cur = tiers.find((t) => t.rank === rank.rank)?.min_lifetime_points ?? 0;
  if (rank.next_rank_at == null) return 312;
  const span = Math.max(1, rank.next_rank_at - cur);
  const p = Math.min(1, Math.max(0, (rank.lifetime_points - cur) / span));
  return Math.round(8 + 304 * p);
}

export function pointsLine(rank: MyRank): string {
  const pts = `${fmtInt(rank.lifetime_points)} pts`;
  return rank.next_rank_name && rank.points_to_next != null ? `${pts} · ${fmtInt(rank.points_to_next)} to ${rank.next_rank_name}` : pts;
}

export function lineColorOf(stop: Stop | undefined): string {
  const c = stop?.routes?.find((r) => r.color)?.color;
  return c ? `#${c}` : COLORS.steelBlue;
}

export const hasLabel = (s: Spot, slug: string) => s.labels.some((l) => l.slug === slug && (l.status === 'declared' || l.status === 'certified'));

/** Badge text: the design's LOCALLY OWNED only when the API says the label is declared or certified; else Demo. */
export function spotBadge(s: Spot): string {
  if (hasLabel(s, 'local-independent')) return 'LOCALLY OWNED';
  return s.demo ? 'Demo' : '';
}

export function ownerDots(s: Spot): { style: string }[] {
  return s.labels
    .filter((l) => (l.status === 'declared' || l.status === 'certified') && OWNER_DOT[l.slug])
    .map((l, k) => ({ style: `display:block;width:18px;height:18px;border-radius:50%;border:2.5px solid #1D3557;background:${OWNER_DOT[l.slug]}${k ? ';margin-left:-6px' : ''}` }));
}

export function bigOffer(o: { kind: string; discount_pct: number | null; points_cost: number | null }): string {
  if (o.kind === 'discount' && o.discount_pct != null) return `${o.discount_pct}% OFF`;
  if (o.kind === 'free_item') return 'FREE';
  if (o.kind === 'points_item' && o.points_cost != null) return `${fmtInt(o.points_cost)} PTS`;
  return '';
}
