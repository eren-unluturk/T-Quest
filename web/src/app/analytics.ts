// View model for the Analytics screen. Pure functions: API data in, strings and SVG geometry out.
// Nothing here is a hard-coded number: every figure comes from the live API responses. Live blocks are computed from
// the MBTA feed stored in Tiger Data; the rider block is demo rider data (synthetic) and is labeled that way in the design.
import type { LeaderEntry, MyAnalytics, MyCollection, MyRank, SystemSnapshot } from '../api/types';
import { COLORS, PALETTE, fmtInt } from './view';

const CHART = { x0: 30, x1: 312, top: 14, base: 112 };
const BARS = { x0: 10, x1: 312, base: 88, maxH: 70 };
const dot = (c: string) => `display:inline-block;width:14px;height:14px;border-radius:50%;border:2.5px solid ${COLORS.navy};background:${c}`;

export interface RiderData { rank: MyRank; collection: MyCollection; me: MyAnalytics; board: LeaderEntry[]; username: string }

/** "3 PM" in Boston time for a 0-23 hour (hour of day). */
export function hourName(h: number): string {
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12} ${h < 12 ? 'AM' : 'PM'}`;
}
const shortHour = (h: number) => `${h % 12 === 0 ? 12 : h % 12}${h < 12 ? 'a' : 'p'}`;
const bostonHour = (iso: string) => hourName(Number(new Intl.DateTimeFormat('en-US', { hour: 'numeric', hour12: false, timeZone: 'America/New_York' }).format(new Date(iso))) % 24);
const plural = (n: number, one: string, many = `${one}s`) => `${fmtInt(n)} ${n === 1 ? one : many}`;
const lineColor = (c: string | null, i: number) => (c ? `#${c}` : PALETTE[i % PALETTE.length]);

export function freshnessText(s: SystemSnapshot): string {
  if (s.freshness_s == null) return 'no recent vehicle data';
  if (s.freshness_s > 300) return `feed is ${Math.round(s.freshness_s / 60)} min behind`;
  return `updated ${s.freshness_s} s ago`;
}

export function buildAnalyticsView(s: SystemSnapshot, rider: RiderData | null) {
  const lineName = new Map(s.lines.map((l) => [l.line_id, l.name]));
  const nameOf = (id: string | null) => (id ? lineName.get(id) ?? id : null);

  // chart 1: complete hours only (the current hour is still filling and would dip), one line per MBTA line
  const hoursSet = [...new Set(s.lines.flatMap((l) => l.series.filter((p) => !p.partial).map((p) => p.hour)))].sort();
  const max = Math.max(1, ...s.lines.flatMap((l) => l.series.filter((p) => !p.partial).map((p) => p.reports)));
  const xAt = (i: number) => (hoursSet.length <= 1 ? (CHART.x0 + CHART.x1) / 2 : CHART.x0 + (i * (CHART.x1 - CHART.x0)) / (hoursSet.length - 1));
  const yAt = (n: number) => +(CHART.base - (n / max) * (CHART.base - CHART.top)).toFixed(1);
  const seen = new Set<string>();
  const seriesLines = s.lines.map((l, i) => {
    const by = new Map(l.series.filter((p) => !p.partial).map((p) => [p.hour, p.reports]));
    const pts = hoursSet.flatMap((h, k) => (by.has(h) ? [[+xAt(k).toFixed(1), yAt(by.get(h)!)]] : []));
    const d = pts.length ? (pts.length === 1 ? `M${pts[0][0] - 2} ${pts[0][1]}L${pts[0][0] + 2} ${pts[0][1]}` : 'M' + pts.map((p) => p.join(' ')).join(' L')) : '';
    const color = lineColor(l.color, i);
    const dash = seen.has(color) ? '6 5' : ''; // two lines share a color (Red and Mattapan): dash the second
    seen.add(color);
    return { d, color, dash };
  }).filter((l) => l.d);
  const tickIdx = hoursSet.length <= 3 ? hoursSet.map((_, k) => k) : [0, Math.floor((hoursSet.length - 1) / 2), hoursSet.length - 1];
  const xTicks = tickIdx.map((k) => ({ x: +Math.min(Math.max(xAt(k), CHART.x0 + 12), CHART.x1 - 14).toFixed(1), label: bostonHour(hoursSet[k]) }));
  const legend = s.lines.map((l, i) => ({ name: l.name, dot: dot(lineColor(l.color, i)) }));
  const chartAlt = hoursSet.length
    ? `Line chart of vehicle position reports per hour for ${s.lines.map((l) => l.name).join(', ')} over the last ${plural(hoursSet.length, 'complete hour')}. The highest hourly count is ${fmtInt(max)}.`
    : 'No complete hours of vehicle data yet.';

  // chart 2: average reports per hour of day (Boston time), hours that have complete data
  const prof = [...s.hourly_profile].sort((a, b) => a.hour - b.hour);
  const pmax = Math.max(1, ...prof.map((p) => p.avg_reports));
  const slot = prof.length ? (BARS.x1 - BARS.x0) / prof.length : 0;
  const bw = Math.min(24, Math.max(6, slot - 6));
  const bars = prof.map((p, i) => {
    const h = Math.max(2, +((p.avg_reports / pmax) * BARS.maxH).toFixed(1));
    const cx = BARS.x0 + slot * i + slot / 2;
    return {
      x: +(cx - bw / 2).toFixed(1), y: +(BARS.base - h).toFixed(1), w: +bw.toFixed(1), h,
      fill: p.hour === s.busiest_hour ? COLORS.red : p.hour === s.quietest_hour ? COLORS.lightBlue : COLORS.yellow,
      lx: +cx.toFixed(1), label: prof.length > 12 && i % 2 ? '' : shortHour(p.hour),
    };
  });
  const maxDays = Math.max(0, ...prof.map((p) => p.days));
  const barsAlt = prof.length
    ? `Bar chart of average vehicle reports for ${plural(prof.length, 'hour')} of the day. Busiest ${s.busiest_hour != null ? hourName(s.busiest_hour) : 'unknown'}, quietest ${s.quietest_hour != null ? hourName(s.quietest_hour) : 'unknown'}.`
    : 'Not enough complete hours collected yet for an hour-of-day chart.';

  const alertsLine = plural(s.active_alerts, 'active alert');
  const affected = s.lines_with_alerts.map((id) => nameOf(id)).filter(Boolean) as string[];

  const tiles = rider
    ? [
        { value: fmtInt(rider.collection.stops.length), label: 'STOPS COLLECTED' },
        { value: rider.me.home_line ? rider.me.home_line : 'none yet', label: 'HOME LINE' },
        { value: fmtInt(rider.rank.lifetime_points), label: 'POINTS' },
        (() => {
          const i = rider.board.findIndex((e) => e.username === rider.username);
          return { value: i >= 0 ? `#${rider.board[i].position}` : 'not ranked', label: `ON THE LEADERBOARD${rider.board.length ? ` OF ${rider.board.length}` : ''}` };
        })(),
      ]
    : ['STOPS COLLECTED', 'HOME LINE', 'POINTS', 'ON THE LEADERBOARD'].map((label) => ({ value: '-', label }));

  return {
    updated: freshnessText(s),
    lines: s.lines.map((l, i) => ({ name: l.name, dot: dot(lineColor(l.color, i)), vehicles: plural(l.vehicles_now, 'vehicle') })),
    alertsLine,
    alertLines: affected.length ? `Subway lines affected: ${affected.join(', ')}` : 'No subway line has an active alert.',
    chartTitle: hoursSet.length ? `Last ${plural(hoursSet.length, 'hour')}, vehicle reports` : 'Vehicle reports, last hours',
    chartAlt, seriesLines, xTicks, yMax: fmtInt(max), legend,
    chartSummary: 'Vehicle position reports per hour from the MBTA feed, complete hours only. More reports means more vehicles running.',
    barsAlt, bars,
    hoursLine: s.busiest_hour != null && s.quietest_hour != null ? `Busiest hour: ${hourName(s.busiest_hour)}. Quietest: ${hourName(s.quietest_hour)}.` : 'Not enough complete hours yet.',
    linesLine: s.busiest_line_24h ? `Busiest line, last 24 h: ${nameOf(s.busiest_line_24h)}. Quietest: ${nameOf(s.quietest_line_24h)}.` : 'No line activity in the last 24 hours.',
    barsNote: prof.length ? `from ${plural(prof.length, 'hour')} with complete data, up to ${plural(maxDays, 'day')} each` : 'we keep collecting; check back later',
    tiles,
    riderNote: rider
      ? `${rider.rank.name}${rider.rank.points_to_next != null && rider.rank.next_rank_name ? ` · ${fmtInt(rider.rank.points_to_next)} to ${rider.rank.next_rank_name}` : ''} · demo rider, not a real person`
      : 'demo rider data is unavailable right now',
  };
}
