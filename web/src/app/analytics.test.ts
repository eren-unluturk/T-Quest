import { describe, expect, it } from 'vitest';
import type { SystemSnapshot } from '../api/types';
import { buildAnalyticsView, freshnessText, hourName } from './analytics';

const snap = (over: Partial<SystemSnapshot> = {}): SystemSnapshot => ({
  generated_at: '2026-11-22T12:00:00Z', last_vehicle_at: '2026-11-22T11:59:00Z', freshness_s: 60, active_alerts: 1, lines_with_alerts: [],
  lines: [{ line_id: 'line-Red', name: 'Red Line', color: 'DA291C', vehicles_now: 1, reports_24h: 10, series: [
    { hour: '2026-11-22T10:00:00Z', reports: 10, partial: false }, { hour: '2026-11-22T11:00:00Z', reports: 30, partial: false }, { hour: '2026-11-22T12:00:00Z', reports: 1, partial: true }] }],
  hourly_profile: [], busiest_hour: null, quietest_hour: null, busiest_line_24h: null, quietest_line_24h: null, ...over,
});

describe('analytics view', () => {
  it('names hours in 12-hour time', () => {
    expect([0, 9, 12, 15, 23].map(hourName)).toEqual(['12 AM', '9 AM', '12 PM', '3 PM', '11 PM']);
  });
  it('drops the partial hour from the chart and scales to the largest complete hour', () => {
    const v = buildAnalyticsView(snap(), null);
    expect(v.seriesLines).toHaveLength(1);
    expect(v.seriesLines[0].d.startsWith('M30 ')).toBe(true);
    expect(v.yMax).toBe('30');
    expect(v.chartAlt).toContain('2 complete hours');
  });
  it('handles no data without throwing and says so in plain words', () => {
    const v = buildAnalyticsView(snap({ lines: [], hourly_profile: [] }), null);
    expect(v.bars).toEqual([]);
    expect(v.hoursLine).toBe('Not enough complete hours yet.');
    expect(v.alertLines).toBe('No subway line has an active alert.');
    expect(v.tiles.every((t) => t.value === '-')).toBe(true);
  });
  it('reports a stale feed instead of "updated"', () => {
    expect(freshnessText(snap({ freshness_s: 900 }))).toBe('feed is 15 min behind');
    expect(freshnessText(snap({ freshness_s: null }))).toBe('no recent vehicle data');
  });
});
