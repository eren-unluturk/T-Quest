// Edge cases found by probing the live MBTA API and the real database.
import { describe, expect, it } from 'vitest';
import { scheduleWindow, verifyRide } from './verify';
import type { Station } from './verify';

const at = (iso: string) => Date.parse(iso);
const park: Station = { id: 'place-pktrm', name: 'Park Street', lat: 42.35639, lon: -71.0624, lines: ['Red'] };
const dtx: Station = { id: 'place-dwnxg', name: 'Downtown Crossing', lat: 42.355518, lon: -71.060225, lines: ['Red', 'Orange'] };

describe('late-night service (the MBTA labels after-midnight trains 24:xx on the previous service day)', () => {
  it('asks for 24:xx times after midnight', () => {
    expect(scheduleWindow(at('2026-11-22T00:30:00-05:00'), at('2026-11-22T00:45:00-05:00'))).toEqual({ min: '24:10', max: '24:55' });
  });
  it('keeps a window that crosses midnight instead of cutting it at 23:59', () => {
    expect(scheduleWindow(at('2026-11-21T23:50:00-05:00'), at('2026-11-22T00:20:00-05:00'))).toEqual({ min: '23:30', max: '24:30' });
  });
  it('starts a new service day at 3 AM', () => {
    expect(scheduleWindow(at('2026-11-22T05:30:00-05:00'), at('2026-11-22T05:40:00-05:00'))).toEqual({ min: '05:10', max: '05:50' });
  });
  it('handles daylight time', () => {
    expect(scheduleWindow(at('2026-07-04T00:30:00-04:00'), at('2026-07-04T00:40:00-04:00'))).toEqual({ min: '24:10', max: '24:50' });
  });
});

describe('ride verification edge cases', () => {
  it('rejects a tap-out before the tap-in (clock skew or tampering)', () => {
    const t = at('2026-11-22T15:00:00-05:00');
    const v = verifyRide({ from: park, to: dtx, t1: t, t2: t - 60000, trips: [], seenTrain: true });
    expect(v.ok).toBe(false);
  });
  it('does not verify a ride to the same station', () => {
    const t = at('2026-11-22T15:00:00-05:00');
    const v = verifyRide({ from: park, to: park, t1: t, t2: t + 600000, trips: [{ id: 'X', route: 'Red', dep: t, arr: t + 600000 }], seenTrain: true });
    expect(v.ok).toBe(false);
  });
});
