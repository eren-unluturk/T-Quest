// Ethnic Boston directions sheet: how to get to a neighborhood's heart on the T from your station.
import type { HoodProps } from './data';
import { metres, nearest } from './geo';
import type { LatLon } from './geo';
import { STOP_MIN, TRANSFER_MIN, routeName, tRoute } from './network';
import type { Network, TRoute } from './network';
import { LINE_COLOR, P, lineOf } from './theme';
import { CloseButton, Dot } from './ui';
import type { Station } from './verify';

const WALK_M_PER_MIN = 80;

export interface DirectionsPlan { hood: HoodProps; hub: LatLon; dest: Station; walkMin: number; route: TRoute | null; total: number | null }

export function planDirections(net: Network, stations: Station[], hood: HoodProps, from: Station): DirectionsPlan | null {
  const hub = { lon: hood.hub[0], lat: hood.hub[1] };
  const dest = nearest(stations, hub);
  if (!dest) return null;
  const walkMin = Math.max(1, Math.round(metres(dest, hub) / WALK_M_PER_MIN));
  const route = tRoute(net, from.id, dest.id);
  return { hood, hub, dest, walkMin, route, total: route ? route.minutes + walkMin : null };
}

const WalkIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={P.navy} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="13" cy="4" r="2" /><path d="M10 21l2-7 3 3v5M9 10l3-3 3 2 2 3M9 10l-2 4" />
  </svg>
);

export function DirectionsSheet({ plan, from, net, nameOf, spotsHref = '#/explore', onClose, onShow }: {
  plan: DirectionsPlan; from: Station; net: Network; nameOf: (id: string) => string;
  spotsHref?: string; onClose: () => void; onShow: () => void;
}) {
  const { hood: h, route: r } = plan;
  return (
    <div className="tqm-sheetwrap" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="tqm-sheet" style={{ paddingTop: 0, gap: 12 }} role="dialog" aria-label={`Directions to ${h.name}`}>
        <div style={{ margin: '0 -18px', padding: '16px 18px 12px', background: h.color, borderBottom: `3px solid ${P.navy}`, borderRadius: '26px 26px 0 0', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
          <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span className="tqm-hand" style={{ fontSize: 20, color: P.red }}>ethnic boston</span>
            <span className="tqm-head" style={{ fontSize: 24, lineHeight: 1.1 }}>{h.name}</span>
            <span style={{ alignSelf: 'flex-start', marginTop: 4, background: '#fff', border: `2px solid ${P.navy}`, borderRadius: 999, padding: '1px 9px', fontSize: 11, fontWeight: 800 }}>{h.heritage}</span>
          </span>
          <CloseButton label="Close" onClick={onClose} />
        </div>
        <p style={{ margin: 0, fontSize: 14, lineHeight: 1.4, fontWeight: 500 }}>{h.blurb}</p>
        <div className="tqm-box" style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span style={{ fontWeight: 800 }}>From {from.name}</span>
            {plan.total != null && <span className="tqm-head" style={{ fontSize: 22 }}>~{plan.total} min</span>}
          </div>
          {!r ? <span style={{ fontWeight: 700 }}>No subway route found from here.</span>
            : r.legs.length === 0 ? <div className="tqm-leg"><Dot color={P.yellow} size={16} /><b>You’re already at {plan.dest.name}</b></div>
              : r.legs.map((l, i) => (
                <div key={i} style={{ display: 'contents' }}>
                  {i > 0 && <div className="tqm-leg change"><span>↻</span><span>Change at <b>{nameOf(l.from)}</b></span></div>}
                  <div className="tqm-leg">
                    <Dot color={LINE_COLOR[lineOf(l.route)]} size={16} />
                    <span style={{ display: 'flex', flexDirection: 'column' }}>
                      <b>Take the {routeName(net, l.route, l)}</b>
                      <span>toward {l.toward} · {l.stops} stop{l.stops > 1 ? 's' : ''}</span>
                      <span>{nameOf(l.from)} → {nameOf(l.to)}</span>
                    </span>
                  </div>
                </div>
              ))}
          <div className="tqm-leg"><WalkIcon />
            <span style={{ display: 'flex', flexDirection: 'column' }}><b>Walk {plan.walkMin} min to {h.heart}</b><span>from {plan.dest.name}</span></span>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <a className="tqm-big" href={spotsHref}>Spots here</a>
          <button type="button" className="tqm-big yellow" onClick={onShow} disabled={!r}>Show on map</button>
        </div>
        <span className="tqm-src">Boundaries: City of Boston / BPDA · Routes: MBTA route patterns · times are estimates ({STOP_MIN} min a stop, {TRANSFER_MIN} min to change)</span>
      </div>
    </div>
  );
}
