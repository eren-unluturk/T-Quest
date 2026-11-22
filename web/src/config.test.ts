import { describe, expect, it } from 'vitest';
import { readConfig } from './config';

describe('readConfig', () => {
  it('uses env urls and strips trailing slashes', () => {
    const c = readConfig({ VITE_DATA_PLATFORM_URL: 'https://a.test/', VITE_INSIGHTS_URL: 'https://b.test', VITE_GAME_URL: 'https://c.test//' }, false);
    expect(c).toEqual({ dp: 'https://a.test', is: 'https://b.test', ge: 'https://c.test' });
  });
  it('falls back to the dev proxy in dev only', () => {
    expect(readConfig({}, true)).toEqual({ dp: '/api/dp', is: '/api/is', ge: '/api/ge' });
    expect(readConfig({ VITE_INSIGHTS_URL: 'https://b.test' }, false)).toEqual({ missing: ['VITE_DATA_PLATFORM_URL', 'VITE_GAME_URL'] });
  });
});
