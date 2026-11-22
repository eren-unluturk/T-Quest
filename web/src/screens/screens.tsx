import { useEffect, useMemo, useState } from 'react';
import { ApiError } from '../api/client';
import type { Fave, Offer } from '../api/types';
import { Frame, Status, useApp, useAsync } from '../app/app';
import {
  CATEGORY_ICON, CATEGORY_MAP, COLORS, OWNER_OPTIONS, PALETTE, bigOffer, buildPlaces, fmtInt, fmtMiles, lineColorOf, ownerDots,
  pointsLine, rankBarX, spotBadge,
} from '../app/view';
import ExploreMarkup from '../design/generated/ExploreMarkup';
import FavesMarkup from '../design/generated/FavesMarkup';
import HomeMarkup from '../design/generated/HomeMarkup';
import LoadingMarkup from '../design/generated/LoadingMarkup';
import ProfileMarkup from '../design/generated/ProfileMarkup';
import TraveledMarkup from '../design/generated/TraveledMarkup';
import { DEMO_STOPS, HOME_STOP, loadSpots } from './data';

const TEAM_CREDIT = 'Written by the T-Quest team. Verify before publishing.';
const loadingOrError = (a: { loading: boolean; error?: Error; reload: () => void; data: unknown }) =>
  !a.data ? <Frame><Status loading={a.loading} error={a.error} reload={a.reload} /></Frame> : null;

// ---------------------------------------------------------------- Loading
export function LoadingScreen() {
  const { api } = useApp();
  const facts = useAsync(() => api.loadingFacts(10), []);
  const [i, setI] = useState(0);
  const list = facts.data ?? [];
  const cur = list.length ? list[i % list.length] : undefined;
  const v = { fact: cur?.body ?? '', next: () => setI((n) => (list.length ? (n + 1) % list.length : 0)) };
  return (
    <Frame dark credits={cur ? [cur.attribution] : []}>
      <LoadingMarkup v={v} />
      <Status loading={facts.loading} error={facts.error} reload={facts.reload} />
    </Frame>
  );
}

// ---------------------------------------------------------------- Home
export function HomeScreen() {
  const { api, session } = useApp();
  const data = useAsync(async () => {
    const [stop, facts, content, faves, rank, tiers, general] = await Promise.all([
      api.stop(HOME_STOP), api.stopFacts(HOME_STOP), api.stopContent(HOME_STOP, 20), api.faves(), api.myRank(), api.rankTiers(), api.loadingFacts(1),
    ]);
    return { stop, facts, content, faves, rank, tiers, general };
  }, []);
  const [sel, setSel] = useState<string | null>(null);
  const [idx, setIdx] = useState(0);
  const [faved, setFaved] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState<Error>();

  const d = data.data;
  useEffect(() => { if (d) setFaved(Object.fromEntries(d.faves.map((f) => [f.fact_id, true]))); }, [d]);
  const places = useMemo(() => {
    if (!d) return [];
    const fallbackText = d.facts.fallback ? d.facts.facts[0]?.body : d.general[0]?.body;
    const own = d.facts.fallback ? [] : d.facts.facts;
    return buildPlaces(d.stop, own, fallbackText, d.content);
  }, [d]);

  const early = loadingOrError(data);
  if (early || !d) return early;

  const place = places.find((p) => p.id === sel) ?? places[0];
  const n = place.facts.length;
  const i = Math.min(idx, Math.max(n - 1, 0));
  const factId = n ? place.facts[i].id : undefined;
  const isFaved = !!(factId && faved[factId]);
  const toggle = async () => {
    if (!factId) return;
    const next = !isFaved;
    setFaved((f) => ({ ...f, [factId]: next }));
    try { await (next ? api.addFave(factId) : api.removeFave(factId)); setErr(undefined); }
    catch (e) { setFaved((f) => ({ ...f, [factId]: !next })); setErr(e as Error); }
  };
  const v = {
    name: session.username() ?? '', avatarInitial: (session.username() ?? '?').slice(0, 1).toUpperCase(),
    rankName: d.rank.name, pointsLine: pointsLine(d.rank), barX: rankBarX(d.rank, d.tiers),
    place: { name: place.name, nearby: place.nearby ?? '' }, hasFacts: n > 0, noFacts: n === 0, fact: n ? place.facts[i].text : '',
    tag: n ? 'did you know?!' : 'no history yet!', tagBg: n ? '#E63946' : '#457B9D',
    faved: isFaved, starFill: isFaved ? COLORS.yellow : 'none', toggleFave: toggle,
    learnHref: place.source ?? d.facts.facts[0]?.source_url ?? '#',
    dots: n > 1 ? place.facts.map((_, k) => ({
      label: `Fact ${k + 1} of ${n}`, pick: () => setIdx(k),
      style: 'display:block;width:12px;height:12px;border-radius:50%;border:2.5px solid #1D3557;box-sizing:border-box;' + (k === i ? 'background:#1D3557' : 'background:#FFFFFF'),
    })) : [],
    pins: places.map((p) => {
      const on = p.id === place.id;
      const s = on ? 48 : 30;
      return {
        name: p.name, sel: on, pick: () => { setSel(p.id); setIdx(0); },
        style: `position:absolute;left:${p.x - s / 2}px;top:${p.y - s / 2}px;width:${s}px;height:${s}px;border-radius:50%;padding:0;cursor:pointer;display:flex;align-items:center;justify-content:center;border:3px solid #1D3557;background:${on ? COLORS.yellow : p.c};${on ? 'box-shadow:3px 3px 0 #1D3557;z-index:2' : ''}`,
        dot: `display:block;border-radius:50%;background:#1D3557;width:${on ? 14 : 8}px;height:${on ? 14 : 8}px`,
      };
    }),
  };
  const credit = place.attribution ?? TEAM_CREDIT;
  return (
    <Frame credits={[`Source: ${credit}${place.source ? ` (${place.source})` : ''}`]}>
      <HomeMarkup v={v} />
      {err && <Status loading={false} error={err} />}
    </Frame>
  );
}

// ---------------------------------------------------------------- Traveled
export function TraveledScreen() {
  const { api } = useApp();
  const data = useAsync(() => api.travel(), []);
  const early = loadingOrError(data);
  if (early || !data.data) return early;
  const t = data.data;
  const miles = (key: string) => fmtMiles(t.per_line.find((l) => l.line_id.toLowerCase().includes(key))?.miles ?? 0);
  const v = {
    spots: [], spot: { name: '', facts: 0, stop: '' }, spotLine: '', unlockedCount: t.unlocked_spots.length,
    totalMiles: fmtMiles(t.total_miles), milesGreen: miles('green'), milesRed: miles('red'), milesBlue: miles('blue'), milesOrange: miles('orange'),
  };
  return <Frame credits={['Miles are straight-line distances between stops (approximate). Map art is a placeholder.']}><TraveledMarkup v={v} /></Frame>;
}

// ---------------------------------------------------------------- Explore
const optStyle = (on: boolean) => 'min-height:40px;padding:6px 12px;border-radius:999px;border:2.5px solid #1D3557;font:700 13px Inter,sans-serif;color:#1D3557;cursor:pointer;display:flex;align-items:center;gap:6px;' + (on ? 'background:#FFC93C;box-shadow:2px 2px 0 #1D3557' : 'background:#FFFFFF');
const CATC: Record<string, string> = { All: '#FFC93C', Sightseeing: '#A8DADC', Restaurants: '#F4A6C6', Drinks: '#B8E0A8', 'Cafés': '#F4A261', Shopping: '#FFE3A3' };

export function ExploreScreen() {
  const { api } = useApp();
  const [cat, setCat] = useState('All');
  const [sheet, setSheet] = useState(false);
  const [owners, setOwners] = useState<Record<string, boolean>>({});
  const slugs = OWNER_OPTIONS.filter((o) => owners[o.key]).map((o) => o.slug);
  const cats = CATEGORY_MAP[cat];
  const data = useAsync(
    () => (cat === 'Sightseeing' ? Promise.resolve({ spots: [], stops: {} }) : loadSpots(api, { category: cats, label: slugs, match: 'all' })),
    [cat, slugs.join(',')],
  );
  if (!data.data) return loadingOrError(data);
  const { spots } = data.data;
  const cards = spots.map(({ spot, stop }, k) => {
    const offer: Offer | undefined = [...spot.offers].sort((a, b) => a.min_rank - b.min_rank)[0];
    return {
      name: spot.name, cat: spot.category.display_name, stop: stop.name, promo: offer?.title ?? '', why: spot.fun_fact ?? '',
      badge: spotBadge(spot), icon: CATEGORY_ICON[spot.category.slug] ?? CATEGORY_ICON.other,
      top: `position:relative;height:96px;background:${PALETTE[k % PALETTE.length]};border-bottom:3px solid #1D3557;display:flex;align-items:center;justify-content:center`,
      lineDot: `display:inline-block;width:10px;height:10px;border-radius:50%;border:2px solid #1D3557;background:${lineColorOf(stop)}`,
      owners: ownerDots(spot),
    };
  });
  const active = slugs.length;
  const v = {
    cats: Object.keys(CATEGORY_MAP).map((c) => ({
      label: c, on: cat === c, pick: () => setCat(c),
      style: 'flex-shrink:0;min-height:42px;padding:6px 14px;border-radius:999px;border:2.5px solid #1D3557;font:700 13px Inter,sans-serif;color:#1D3557;cursor:pointer;' + (cat === c ? `background:${CATC[c]};box-shadow:3px 3px 0 #1D3557` : 'background:#FFFFFF'),
    })),
    sections: [{ title: 'Explore', sub: '', subColor: '#457B9D', cards, empty: cards.length === 0 }],
    sheetOpen: sheet, openSheet: () => setSheet(true), closeSheet: () => setSheet(false),
    clearAll: () => setOwners({}), hasActive: active > 0, activeCount: active, resultCount: cards.length,
    ethnic: false, ethnicBg: '#FFFFFF', ethnicSide: 'flex-start', toggleEthnic: () => undefined,
    lineOpts: [],
    ownerOpts: OWNER_OPTIONS.map((o) => ({
      label: o.label, on: !!owners[o.key], style: optStyle(!!owners[o.key]),
      dot: `display:inline-block;width:12px;height:12px;border-radius:50%;border:2px solid #1D3557;background:${o.dot}`,
      pick: () => setOwners((s) => ({ ...s, [o.key]: !s[o.key] })),
    })),
  };
  return (
    <Frame credits={['Sponsors, shops, offers and labels shown here are demo placeholders. Only declared or certified labels are shown.']}>
      <ExploreMarkup v={v} />
      <Status loading={data.loading} error={data.error} reload={data.reload} />
    </Frame>
  );
}

// ---------------------------------------------------------------- Faves
export function FavesScreen() {
  const { api } = useApp();
  const data = useAsync(() => api.faves(), []);
  const [err, setErr] = useState<Error>();
  const early = loadingOrError(data);
  if (early || !data.data) return early;
  const rot = [-1, 1, -0.8, 0.8, -0.6];
  const items = data.data.map((f: Fave, k: number) => ({
    place: f.place ?? '', fact: f.text,
    lineDot: `display:inline-block;width:14px;height:14px;border-radius:50%;border:2.5px solid #1D3557;background:${COLORS.steelBlue}`,
    card: `background:${PALETTE[k % PALETTE.length]};border:3px solid #1D3557;border-radius:18px;box-shadow:4px 4px 0 #1D3557;padding:12px 14px;display:flex;flex-direction:column;gap:6px;transform:rotate(${rot[k % rot.length]}deg)`,
    unfave: async () => { try { await api.removeFave(f.fact_id); data.reload(); } catch (e) { setErr(e as Error); } },
  }));
  const credits = [...new Set(data.data.map((f) => f.attribution))];
  return (
    <Frame credits={credits}>
      <FavesMarkup v={{ items, count: items.length, empty: items.length === 0 }} />
      {err && <Status loading={false} error={err} />}
    </Frame>
  );
}

// ---------------------------------------------------------------- Profile
export function ProfileScreen() {
  const { api, session } = useApp();
  const data = useAsync(async () => {
    const [rank, points, tiers] = await Promise.all([api.myRank(), api.myPoints(), api.rankTiers()]);
    const [now, next, spots] = await Promise.all([api.offers({ rank: rank.rank }), rank.next_rank ? api.offers({ rank: rank.next_rank }) : Promise.resolve([]), loadSpots(api)]);
    return { rank, points, tiers, now, next, spots: spots.spots };
  }, []);
  const early = loadingOrError(data);
  if (early || !data.data) return early;
  const d = data.data;
  const at = (o: Offer) => d.spots.find((s) => s.spot.sponsor_id === o.sponsor_id);
  const card = (o: Offer, k: number, locked: boolean) => ({
    name: at(o)?.spot.name ?? '', where: at(o)?.stop.name ?? '', big: bigOffer(o), who: o.title,
    detail: locked && d.rank.points_to_next != null ? `${fmtInt(d.rank.points_to_next)} points to go!` : o.description,
    tag: locked ? 'LOCKED · KEEP RIDING' : at(o) ? spotBadge(at(o)!.spot) : 'Demo',
    card: 'flex-shrink:0;width:200px;background:#FFFFFF;border:3px solid #1D3557;border-radius:20px;overflow:hidden;display:flex;flex-direction:column;' + (locked ? 'border-style:dashed;opacity:0.85' : 'box-shadow:4px 4px 0 #1D3557'),
    top: `background:${locked ? '#E6E1D6' : PALETTE[k % PALETTE.length]};border-bottom:3px dashed #1D3557;padding:12px;display:flex;flex-direction:column;gap:2px`,
  });
  const unlocked = d.now.slice(0, 8).map((o, k) => card(o, k, false));
  const lockedOne = d.next.find((o) => o.min_rank === d.rank.next_rank);
  const v = {
    username: session.username() ?? '', rankName: d.rank.name, pointsText: fmtInt(d.points.lifetime),
    toNext: d.rank.next_rank_name && d.rank.points_to_next != null ? `· ${fmtInt(d.rank.points_to_next)} to ${d.rank.next_rank_name}!` : '',
    offers: [...unlocked, ...(lockedOne ? [card(lockedOne, unlocked.length, true)] : [])],
  };
  return <Frame credits={['Offers are demo placeholders with placeholder discount percentages. No real discount is implied.']}><ProfileMarkup v={v} /></Frame>;
}

// ---------------------------------------------------------------- Stubs (no design yet)
const stubBox = { padding: 20, fontFamily: 'Inter, system-ui, sans-serif', color: '#1D3557', background: '#FFF8EC', minHeight: 844, boxSizing: 'border-box' as const };

export function Stub({ title, endpoints, children }: { title: string; endpoints: string[]; children?: React.ReactNode }) {
  return (
    <Frame>
      <div style={stubBox}>
        <h1 style={{ marginTop: 0 }}>{title}</h1>
        <p><strong>No design yet.</strong></p>
        <p>Endpoints this screen will use:</p>
        <ul>{endpoints.map((e) => <li key={e}><code>{e}</code></li>)}</ul>
        {children}
        <p><a href="#/home">Home</a> · <a href="#/explore">Explore</a> · <a href="#/traveled">Traveled</a> · <a href="#/profile">Profile</a></p>
      </div>
    </Frame>
  );
}

export function LoginStub({ onDone }: { onDone: () => void }) {
  const { api, session } = useApp();
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string>();
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(undefined);
    try {
      const r = await api.login(name.trim());
      session.set(r.token, r.username, r.expires_in);
      onDone();
    } catch (x) {
      setErr(x instanceof ApiError ? x.message : 'sign-in failed');
    } finally {
      setBusy(false);
    }
  };
  return (
    <Stub title="Sign in" endpoints={['POST insights /auth/demo-login']}>
      <form onSubmit={submit}>
        <label>
          Sandbox username (3-32 letters or digits, no personal data){' '}
          <input value={name} onChange={(e) => setName(e.target.value)} pattern="[A-Za-z0-9]{3,32}" minLength={3} maxLength={32} required autoComplete="off" />
        </label>{' '}
        <button type="submit" disabled={busy}>Sign in</button>
      </form>
      {err && <p role="alert">{err}</p>}
    </Stub>
  );
}

export function CheckInStub() {
  const { api } = useApp();
  const [msg, setMsg] = useState<string>();
  const go = async () => {
    try {
      const stop = await api.stop(HOME_STOP);
      const r = await api.checkin({ stop_id: HOME_STOP, lat: stop.lat, lon: stop.lon, client_time: new Date().toISOString() });
      setMsg(`+${r.points_awarded} points${r.new_rank ? `, new rank ${r.new_rank}` : ''}`);
    } catch (e) {
      setMsg((e as Error).message);
    }
  };
  return (
    <Stub title="Check in" endpoints={['GET data-platform /stops/{id}', 'POST game-engine /checkins', 'GET game-engine /me/points', 'GET game-engine /me/rank']}>
      <button type="button" onClick={go}>Check in at {DEMO_STOPS.length ? 'the demo stop' : ''}</button>
      {msg && <p role="status">{msg}</p>}
    </Stub>
  );
}

export function MoreStub() {
  return <Stub title="Friends, leaderboard, quests, redemptions" endpoints={['GET game-engine /friends', 'POST game-engine /friends', 'GET game-engine /leaderboards', 'GET game-engine /quests', 'POST game-engine /redemptions', 'GET insights /offers', 'GET insights /physical-rewards/catalog']} />;
}
