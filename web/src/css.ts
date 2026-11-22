import type { CSSProperties } from 'react';

/** Turns the design's inline CSS strings ("a:b;c:d") into a React style object. */
export function css(s: string | undefined | null): CSSProperties {
  const out: Record<string, string> = {};
  if (!s) return out;
  for (const decl of s.split(';')) {
    const i = decl.indexOf(':');
    if (i < 0) continue;
    const key = decl.slice(0, i).trim();
    const val = decl.slice(i + 1).trim();
    if (!key) continue;
    out[key.replace(/-([a-z])/g, (_, c: string) => c.toUpperCase())] = val;
  }
  return out as CSSProperties;
}
