// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { Session } from '../api/session';
import type { Api } from '../api/client';
import { AppProvider } from '../app/app';

const stop = (id: string, name: string, lat: number, lon: number) => ({ id, name, lat, lon, routes: [{ id: 'Red', color: 'DA291C', line_id: 'line-Red', short_name: 'Red', mode: 'subway' }] });
const label = (slug: string, name: string) => ({ slug, display_name: name, status: 'declared' as const, evidence_url: null, declaration_note: 'x' });
const spot = (id: string, name: string, labels: ReturnType<typeof label>[], sponsored = false) => ({
  id, name, category: { slug: 'cafe', display_name: 'Cafe' }, address: null, placement_type: sponsored ? 'sponsored' as const : 'listed' as const, demo: true,
  sponsor_id: sponsored ? 'sp1' : null, distance_m: 100, fun_fact: `fun fact of ${name}`, labels,
  offers: sponsored ? [{ id: 'o1', sponsor_id: 'sp1', store_id: null, title: 'Rank 1 discount (demo)', description: 'd', kind: 'discount' as const, discount_pct: 3, points_cost: null, min_rank: 1, placement: 'local_pick' as const, demo: true }] : [],
});
const TEAM = 'Written by the T-Quest team. Verify before publishing.';

function fakeApi(over: Partial<Api> = {}): Api {
  const rank = { rank: 2, name: 'Town Crier', avatar_key: 'town-crier', discount_pct: 4, lifetime_points: 1000, next_rank: 3, next_rank_name: 'Lamplighter', next_rank_at: 1500, points_to_next: 500 };
  const nearby = (id: string) => ({
    stop_id: id, total: 2, limit: 100, offset: 0, facets: { categories: [], labels: [] },
    spots: id === 'place-harsq' ? [spot('a', 'Sample Roasters (demo)', [label('local-independent', 'Local / independent'), label('woman-owned', 'Woman-owned')]), spot('b', 'Mint Julep', [], true)] : [],
  });
  return {
    login: async (u) => ({ token: 'T', username: u, expires_in: 3600 }),
    loadingFacts: async () => [{ id: 'l1', body: 'Harvard was founded in 1636.', tags: [], source_url: null, attribution: TEAM }],
    stop: async (id) => stop(id, id === 'place-pktrm' ? 'Park Street' : id.replace('place-', ''), 42.3564, -71.0624),
    vehicles: async () => [], lines: async () => [],
    travel: async () => ({ total_miles: 12.34, per_line: [{ line_id: 'line-Red', name: 'Red Line', color: 'DA291C', miles: 12.3 }, { line_id: 'line-Green', name: 'Green Line', color: null, miles: 0 }], traveled_segments: [], unlocked_spots: [] }),
    stopFacts: async () => ({ stop_id: 'place-pktrm', stop_name: 'Park Street', facts: [{ id: 'f1', kind: 'history', title: 't', body: 'Park Street opened in 1897.', source_url: 'https://example.test/src' }], fallback: false, note: null }),
    stopContent: async () => [],
    nearby: async (id) => nearby(id),
    categories: async () => [], labels: async () => [],
    faves: async () => [{ fact_id: 'f1', kind: 'stop_fact', text: 'Park Street opened in 1897.', place: 'Park Street', line: null, attribution: TEAM, source_url: null, faved_at: '2026-01-01T00:00:00Z' }],
    addFave: async () => undefined, removeFave: async () => undefined,
    rankTiers: async () => [{ rank: 2, name: 'Town Crier', avatar_key: 'town-crier', min_lifetime_points: 500, discount_pct: 4, free_item: false, demo: true, offers: [] }],
    offers: async () => [],
    myRank: async () => rank,
    myPoints: async () => ({ balance: 1000, lifetime: 1000, recent: [] }),
    checkin: async () => ({ checkin_id: 'c', points_awarded: 20, first_visit: true, new_rank: null, badges_unlocked: [] }),
    ...over,
  };
}

function mount(hash: string, api: Api = fakeApi(), loggedIn = true) {
  const session = new Session();
  if (loggedIn) session.set('T', 'riderOne', 3600);
  window.location.hash = hash;
  return render(<AppProvider value={{ api, session }}><App /></AppProvider>);
}

afterEach(() => cleanup());

describe('screens (ported design wired to API data)', () => {
  it('shows the sign-in stub when logged out and says there is no design yet', () => {
    mount('#/home', fakeApi(), false);
    expect(screen.getByText(/No design yet/)).toBeTruthy();
    expect(screen.getByText(/POST insights \/auth\/demo-login/)).toBeTruthy();
  });

  it('Loading shows an API fact with its attribution and the demo footer', async () => {
    mount('#/loading');
    await waitFor(() => expect(screen.getByText('Harvard was founded in 1636.')).toBeTruthy());
    expect(screen.getAllByText(/Written by the T-Quest team/).length).toBeGreaterThan(0);
    expect(screen.getByText('Demo. Not affiliated with the MBTA or any sponsor. Transit data from the MBTA.')).toBeTruthy();
  });

  it('Home shows rank, points and the stop fact from the API, no leftover placeholder text', async () => {
    const { container } = mount('#/home');
    await waitFor(() => expect(screen.getByText('Park Street opened in 1897.')).toBeTruthy());
    expect(screen.getByText('Town Crier')).toBeTruthy();
    expect(screen.getByText('1,000 pts · 500 to Lamplighter')).toBeTruthy();
    expect(screen.getByText('hey riderOne!')).toBeTruthy();
    expect(container.textContent).not.toMatch(/\[name\]|\[your|1,240|Boston Lobstah/);
  });

  it('Home shows the error and a retry when a backend fails', async () => {
    mount('#/home', fakeApi({ myRank: async () => { throw new Error('game-engine is unreachable'); } }));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('game-engine is unreachable'));
    expect(screen.getByText('Retry')).toBeTruthy();
  });

  it('Explore marks spots Demo, shows LOCALLY OWNED only with a declared label, and no design placeholder stores', async () => {
    const { container } = mount('#/explore');
    await waitFor(() => expect(screen.getByText('Sample Roasters (demo)')).toBeTruthy());
    expect(screen.getByText('Mint Julep')).toBeTruthy();
    expect(screen.getAllByText('Demo').length).toBe(1); // Mint Julep: demo, no label
    expect(screen.getAllByText('LOCALLY OWNED').length).toBe(1); // the sample spot with a declared label
    expect(screen.getByText('Rank 1 discount (demo)')).toBeTruthy();
    expect(container.textContent).not.toMatch(/Abuela|Steep & Swirl|Roxbury Roots/);
  });

  it('Traveled shows real miles from the API, not the design placeholders', async () => {
    const { container } = mount('#/traveled');
    await waitFor(() => expect(screen.getAllByText('12.3').length).toBe(2)); // total and the Red tile
    expect(container.textContent).toContain('0 unlocked!');
    expect(container.textContent).not.toContain('7 unlocked!');
  });

  it('Faves lists faved facts with attribution; Profile uses the real rank', async () => {
    mount('#/faves');
    await waitFor(() => expect(screen.getByText('Park Street opened in 1897.')).toBeTruthy());
    cleanup();
    const { container } = mount('#/profile');
    await waitFor(() => expect(container.textContent).toContain('@riderOne · Town Crier'));
    expect(container.textContent).not.toMatch(/\[username\]|\[#0042\]/);
  });

  it('stub screens never invent a layout', () => {
    mount('#/checkin');
    expect(screen.getByText(/No design yet/)).toBeTruthy();
    expect(screen.getByText(/POST game-engine \/checkins/)).toBeTruthy();
  });

  it('does not store the token in browser storage', async () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem');
    mount('#/home');
    await waitFor(() => expect(screen.getByText('Town Crier')).toBeTruthy());
    expect(spy).not.toHaveBeenCalled();
  });
});
