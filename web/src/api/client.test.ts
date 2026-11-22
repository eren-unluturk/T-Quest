import { describe, expect, it, vi } from 'vitest';
import { ApiError, createApi } from './client';
import { Session } from './session';

const cfg = { dp: 'http://dp', is: 'http://is', ge: 'http://ge' };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

function setup(handler: (url: string, init: RequestInit) => Response | Promise<Response>) {
  const session = new Session();
  session.set('TOK', 'rider1', 3600);
  const f = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => handler(String(url), init ?? {}));
  return { api: createApi(cfg, session, f as unknown as typeof fetch, 200), session, f };
}

describe('api client', () => {
  it('sends the bearer token and builds query strings with repeated params', async () => {
    const { api, f } = setup(() => json({ stop_id: 'x', spots: [], facets: { categories: [], labels: [] } }));
    await api.nearby('place-harsq', { category: ['cafe', 'bar'], label: ['woman-owned'], match: 'any', sponsored: false });
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('http://is/stops/place-harsq/nearby?category=cafe&category=bar&label=woman-owned&match=any&sponsored=false');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer TOK');
  });

  it('login does not need a token and posts the username', async () => {
    const session = new Session();
    const f = vi.fn(async () => json({ token: 'T', username: 'riderTwo', expires_in: 60 }));
    const api = createApi(cfg, session, f as unknown as typeof fetch);
    const r = await api.login('riderTwo');
    expect(r.token).toBe('T');
    const [, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.method).toBe('POST');
    expect(init.body).toBe(JSON.stringify({ username: 'riderTwo' }));
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it('refuses to call a protected route without a session (no request is made)', async () => {
    const f = vi.fn();
    const api = createApi(cfg, new Session(), f as unknown as typeof fetch);
    await expect(api.myRank()).rejects.toMatchObject({ status: 401 });
    expect(f).not.toHaveBeenCalled();
  });

  it('a 401 from the server signs the user out', async () => {
    const { api, session } = setup(() => json({ detail: 'invalid or missing credentials' }, 401));
    await expect(api.faves()).rejects.toBeInstanceOf(ApiError);
    expect(session.isLoggedIn()).toBe(false);
  });

  it('maps errors to readable ApiError messages', async () => {
    const { api } = setup(() => json({ detail: 'cooldown' }, 409));
    await expect(api.checkin({ stop_id: 'a', lat: 1, lon: 2, client_time: 'x' })).rejects.toMatchObject({ status: 409, message: expect.stringContaining('cooldown') });
  });

  it('reports an unreachable backend and a slow backend', async () => {
    const down = setup(() => { throw new TypeError('network'); });
    await expect(down.api.myRank()).rejects.toMatchObject({ status: 0, message: expect.stringContaining('unreachable') });
    const slow = setup((_u, init) => new Promise((_res, rej) => { init.signal?.addEventListener('abort', () => rej(new DOMException('aborted', 'AbortError'))); }));
    await expect(slow.api.myRank()).rejects.toMatchObject({ status: 0, message: expect.stringContaining('too long') });
  });

  it('handles 204 and unreadable bodies', async () => {
    const ok = setup(() => new Response(null, { status: 204 }));
    await expect(ok.api.addFave('abc')).resolves.toBeUndefined();
    const bad = setup(() => new Response('<html>', { status: 200 }));
    await expect(bad.api.rankTiers()).rejects.toMatchObject({ message: expect.stringContaining('unreadable') });
  });

  it('url-encodes ids', async () => {
    const { api, f } = setup(() => new Response(null, { status: 204 }));
    await api.removeFave('a/b c');
    expect(String(f.mock.calls[0][0])).toBe('http://is/me/faves/a%2Fb%20c');
  });
});
