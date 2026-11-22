import { describe, expect, it } from 'vitest';
import { Session } from './session';

describe('Session', () => {
  it('holds a token until it expires', () => {
    let t = 1_000_000;
    const s = new Session(() => t);
    expect(s.isLoggedIn()).toBe(false);
    s.set('tok', 'rider1', 60);
    expect(s.token()).toBe('tok');
    expect(s.username()).toBe('rider1');
    t += 54_000; // 6 s left
    expect(s.token()).toBe('tok');
    t += 2_000; // inside the 5 s safety margin
    expect(s.token()).toBeNull();
    expect(s.username()).toBeNull();
  });

  it('clear() signs out and notifies subscribers once', () => {
    const s = new Session();
    let n = 0;
    s.subscribe(() => n++);
    s.set('tok', 'rider1', 60);
    s.clear();
    s.clear();
    expect(s.token()).toBeNull();
    expect(n).toBe(2); // set + first clear
  });

  it('never touches browser storage', () => {
    const calls: string[] = [];
    const fake = { getItem: () => (calls.push('get'), null), setItem: () => calls.push('set'), removeItem: () => calls.push('rm') };
    // @ts-expect-error test double
    globalThis.localStorage = fake;
    // @ts-expect-error test double
    globalThis.sessionStorage = fake;
    const s = new Session();
    s.set('tok', 'rider1', 60);
    s.token();
    s.clear();
    expect(calls).toEqual([]);
  });
});
