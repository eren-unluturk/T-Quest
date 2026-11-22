import type { ApiConfig } from '../config';
import { Session } from './session';
import type {
  CategoryRef, CheckinRequest, CheckinResult, ContentItem, Fave, LabelType, Line, LoadingFact, LoginResponse, MyPoints, MyRank,
  Nearby, Offer, RankTier, Stop, StopFacts, Travel, Vehicle,
} from './types';

export class ApiError extends Error {
  constructor(public status: number, message: string, public service: string) {
    super(message);
    this.name = 'ApiError';
  }
}

type Service = keyof ApiConfig;
const NAMES: Record<Service, string> = { dp: 'data-platform', is: 'insights-sponsors', ge: 'game-engine' };

export interface NearbyParams {
  category?: string[]; label?: string[]; match?: 'any' | 'all'; sponsored?: boolean; include_demo?: boolean;
  q?: string; sort?: 'distance' | 'name' | 'sponsored_first'; limit?: number; offset?: number;
}

export interface Api {
  login(username: string): Promise<LoginResponse>;
  loadingFacts(limit?: number): Promise<LoadingFact[]>;
  stop(id: string): Promise<Stop>;
  vehicles(routeId?: string): Promise<Vehicle[]>;
  lines(): Promise<Line[]>;
  travel(): Promise<Travel>;
  stopFacts(stopId: string): Promise<StopFacts>;
  stopContent(stopId: string, limit?: number): Promise<ContentItem[]>;
  nearby(stopId: string, params?: NearbyParams): Promise<Nearby>;
  categories(): Promise<CategoryRef[]>;
  labels(): Promise<LabelType[]>;
  faves(): Promise<Fave[]>;
  addFave(factId: string): Promise<void>;
  removeFave(factId: string): Promise<void>;
  rankTiers(): Promise<RankTier[]>;
  offers(params?: { stop_id?: string; rank?: number }): Promise<Offer[]>;
  myRank(): Promise<MyRank>;
  myPoints(): Promise<MyPoints>;
  checkin(body: CheckinRequest): Promise<CheckinResult>;
}

export function createApi(cfg: ApiConfig, session: Session, fetchImpl: typeof fetch = (...a) => fetch(...a), timeoutMs = 12000): Api {
  async function request<T>(svc: Service, path: string, opts: { method?: string; body?: unknown; auth?: boolean } = {}): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (opts.auth !== false) {
      const tok = session.token();
      if (!tok) throw new ApiError(401, 'not signed in', NAMES[svc]);
      headers.Authorization = `Bearer ${tok}`;
    }
    if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), timeoutMs);
    let res: Response;
    try {
      res = await fetchImpl(cfg[svc] + path, {
        method: opts.method ?? 'GET', headers, signal: ctl.signal,
        body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      });
    } catch (e) {
      const aborted = e instanceof DOMException && e.name === 'AbortError';
      throw new ApiError(0, aborted ? `${NAMES[svc]} took too long` : `${NAMES[svc]} is unreachable`, NAMES[svc]);
    } finally {
      clearTimeout(timer);
    }
    if (res.status === 401) session.clear(); // expired or invalid: sign out
    if (!res.ok) {
      let detail = '';
      try {
        const j = await res.json();
        detail = typeof j?.detail === 'string' ? j.detail : '';
      } catch { /* generic body */ }
      throw new ApiError(res.status, `${NAMES[svc]}: HTTP ${res.status}${detail ? ` (${detail})` : ''}`, NAMES[svc]);
    }
    if (res.status === 204) return undefined as T;
    try {
      return (await res.json()) as T;
    } catch {
      throw new ApiError(res.status, `${NAMES[svc]} returned an unreadable response`, NAMES[svc]);
    }
  }

  const qs = (o: Record<string, unknown>) => {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(o)) {
      if (v === undefined || v === null || v === '') continue;
      if (Array.isArray(v)) v.forEach((x) => p.append(k, String(x)));
      else p.append(k, String(v));
    }
    const s = p.toString();
    return s ? `?${s}` : '';
  };
  const enc = encodeURIComponent;

  return {
    login: (username) => request('is', '/auth/demo-login', { method: 'POST', body: { username }, auth: false }),
    loadingFacts: (limit = 10) => request('is', `/loading-facts${qs({ limit })}`, { auth: false }),
    stop: (id) => request('dp', `/stops/${enc(id)}`, { auth: false }),
    vehicles: (routeId) => request('dp', `/vehicles${qs({ route_id: routeId })}`, { auth: false }),
    lines: () => request('dp', '/lines', { auth: false }),
    travel: () => request('dp', '/me/travel'),
    stopFacts: (id) => request('is', `/stops/${enc(id)}/facts`),
    stopContent: (id, limit = 12) => request('is', `/stops/${enc(id)}/content${qs({ limit })}`),
    nearby: (id, p = {}) => request('is', `/stops/${enc(id)}/nearby${qs({ ...p })}`),
    categories: () => request('is', '/categories'),
    labels: () => request('is', '/labels'),
    faves: () => request('is', '/me/faves'),
    addFave: (id) => request('is', `/me/faves/${enc(id)}`, { method: 'POST' }),
    removeFave: (id) => request('is', `/me/faves/${enc(id)}`, { method: 'DELETE' }),
    rankTiers: () => request('is', '/rank-tiers'),
    offers: (p = {}) => request('is', `/offers${qs({ ...p })}`),
    myRank: () => request('ge', '/me/rank'),
    myPoints: () => request('ge', '/me/points'),
    checkin: (body) => request('ge', '/checkins', { method: 'POST', body }),
  };
}
