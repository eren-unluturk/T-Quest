/** Base URLs come from the environment. In dev they default to the Vite proxy paths (see vite.config.ts). */
export interface ApiConfig {
  dp: string; // data-platform
  is: string; // insights-sponsors
  ge: string; // game-engine
}

const strip = (u: string) => u.replace(/\/+$/, '');

export function readConfig(env: Record<string, string | undefined> = import.meta.env as Record<string, string | undefined>, dev = import.meta.env.DEV): ApiConfig | { missing: string[] } {
  const pick = (name: string, devDefault: string) => {
    const v = env[name];
    if (v && v.trim()) return strip(v.trim());
    return dev ? devDefault : '';
  };
  const cfg = {
    dp: pick('VITE_DATA_PLATFORM_URL', '/api/dp'),
    is: pick('VITE_INSIGHTS_URL', '/api/is'),
    ge: pick('VITE_GAME_URL', '/api/ge'),
  };
  const missing = [
    !cfg.dp && 'VITE_DATA_PLATFORM_URL',
    !cfg.is && 'VITE_INSIGHTS_URL',
    !cfg.ge && 'VITE_GAME_URL',
  ].filter(Boolean) as string[];
  return missing.length ? { missing } : cfg;
}

/** Credits for the data sources shown on every screen. */
export const FOOTER = 'Demo. Not affiliated with the MBTA or any sponsor. Transit data from the MBTA.';
export const DATA_CREDITS = [
  'MBTA V3 API and GTFS (MassDOT Developers License)',
  'Analyze Boston, City of Boston (PDDL)',
  'Digital Commonwealth (items with open rights)',
  'Freedom Trail facts written by the T-Quest team',
];
