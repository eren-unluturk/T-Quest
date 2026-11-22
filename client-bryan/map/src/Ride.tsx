// Tap in, pick where you get off, tap out; then the stamp shows whether a real train made that trip.
// Not in the canvas yet: a proposal for Isabella, drawn in her style.
import { useMemo, useState } from 'react';
import { scheduledTrips } from './data';
import type { MapServices, Vehicle } from './data';
import { metres } from './geo';
import { LINE_COLOR, P, lineOf } from './theme';
import type { Line } from './theme';
import { CloseButton, Dot } from './ui';
import { verifyRide } from './verify';
import type { RideVerdict, Station } from './verify';

const LOOKAHEAD_MS = 90 * 60000;
const SEEN_M = 400;

export interface VerifiedRide { from: Station; to: Station; line: Line; tapIn: Date; tapOut: Date; tripId: string }
/** What the host app reports back after recording a verified ride (e.g. a game-engine check-in). */
export interface RideReward { points?: number | null; note?: string }
export interface RideOutcome extends RideVerdict { from: Station; to: Station; line: Line; reward: RideReward }

export function RideSheet({ services, from, stations, vehicles, onClose, onDone }: {
  services: MapServices; from: Station; stations: Station[]; vehicles: Vehicle[];
  onClose: () => void; onDone: (r: { from: Station; to: Station; line: Line; t1: number; t2: number; seenTrain: boolean }) => void;
}) {
  const [t1] = useState(() => Date.now());
  const [line, setLine] = useState<Line>(() => (from.lines.includes('Red') ? 'Red' : from.lines[0]) as Line);
  // live evidence at tap-in: a real train on this line within 400 m of the station right now (data-platform /vehicles)
  const seen = useMemo(() => vehicles
    .filter((v) => lineOf(v.route_id!) === line)
    .map((v) => ({ v, d: metres(from, { lat: v.lat!, lon: v.lon! }) }))
    .sort((a, b) => a.d - b.d)[0], [vehicles, line, from]);
  const seenTrain = !!seen && seen.d < SEEN_M;
  const dests = useMemo(() => stations
    .filter((s) => s.id !== from.id && s.lines.includes(line))
    .map((s) => ({ ...s, d: metres(from, s) }))
    .sort((a, b) => a.d - b.d).slice(0, 6), [stations, from, line]);
  const [toId, setToId] = useState<string>();
  const to = dests.find((d) => d.id === toId) ?? dests[0];
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const rideThere = async () => {
    setBusy(true);
    try {
      const trip = (await scheduledTrips(services, from.id, to.id, line, t1, t1 + LOOKAHEAD_MS)).find((t) => t.dep >= t1 - 60000);
      if (!trip) { setMsg(`No scheduled ${line} Line train from ${from.name} to ${to.name} in the next 90 min.`); return; }
      onDone({ from, to, line, t1, t2: trip.arr, seenTrain });
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="tqm-sheetwrap" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="tqm-sheet" role="dialog" aria-label="Ride">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ display: 'flex', flexDirection: 'column' }}>
            <span className="tqm-hand" style={{ fontSize: 20, color: LINE_COLOR[line] }}>tapped in!</span>
            <span className="tqm-head" style={{ fontSize: 22 }}>{from.name} · {line} Line</span>
          </span>
          <CloseButton label="Cancel ride" onClick={onClose} />
        </div>
        {from.lines.length > 1 && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {from.lines.map((l) => (
              <button type="button" key={l} className={`tqm-pill${l === line ? ' on' : ''}`} aria-pressed={l === line} onClick={() => { setLine(l as Line); setToId(undefined); }}>
                <Dot color={LINE_COLOR[l as Line]} />{l} Line
              </button>
            ))}
          </div>
        )}
        <span style={{ fontSize: 12, fontWeight: 700, color: P.steel }}>
          {seenTrain ? `Live train ${seen!.v.label ?? seen!.v.vehicle_id} seen ${Math.round(seen!.d)} m from the station` : 'No live train near the station right now'}
        </span>
        <span style={{ fontSize: 13, fontWeight: 800 }}>Where are you getting off?</span>
        <div className="tqm-stops">
          {dests.map((d) => (
            <button type="button" key={d.id} className={d.id === to?.id ? 'on' : ''} aria-pressed={d.id === to?.id} onClick={() => setToId(d.id)}>
              <Dot color={LINE_COLOR[line]} />{d.name}<small>{(d.d / 1609).toFixed(1)} mi</small>
            </button>
          ))}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <button type="button" className="tqm-big" disabled={busy || !to} onClick={() => onDone({ from, to, line, t1, t2: Date.now(), seenTrain })}>Tap out now</button>
          <button type="button" className="tqm-big yellow" disabled={busy || !to} onClick={rideThere}>Ride there ⏩</button>
        </div>
        <span className="tqm-src">demo: “Ride there” skips the clock ahead to when the next real scheduled train arrives. “Tap out now” is what a GPS spoofer would do.</span>
        {msg && <div className="tqm-box" style={{ padding: 10, fontSize: 13, fontWeight: 700 }}>{msg}</div>}
      </div>
    </div>
  );
}

/** Checks a finished ride against real MBTA trips, and lets the host record it when it passes. */
export async function finishRide(
  services: MapServices,
  r: { from: Station; to: Station; line: Line; t1: number; t2: number; seenTrain: boolean },
  onVerified?: (ride: VerifiedRide) => Promise<RideReward | void>,
): Promise<RideOutcome> {
  const trips = await scheduledTrips(services, r.from.id, r.to.id, r.line, r.t1, r.t2).catch(() => []);
  const verdict = verifyRide({ from: r.from, to: r.to, t1: r.t1, t2: r.t2, trips, seenTrain: r.seenTrain });
  let reward: RideReward = {};
  if (verdict.ok && onVerified) {
    try {
      reward = (await onVerified({ from: r.from, to: r.to, line: r.line, tapIn: new Date(r.t1), tapOut: new Date(r.t2), tripId: verdict.trip!.id })) ?? {};
    } catch (e) {
      reward = { note: (e as Error).message };
    }
  }
  return { ...verdict, from: r.from, to: r.to, line: r.line, reward };
}

export function Stamp({ r, traveledHref = '#/traveled', onClose }: { r: RideOutcome; traveledHref?: string; onClose: () => void }) {
  const color = r.ok ? LINE_COLOR[r.line] : P.red;
  return (
    <div className="tqm-stampwrap" role="dialog" aria-label={r.ok ? 'Ride verified' : 'Ride not verified'}>
      <div className="tqm-stamp" style={{ borderColor: color, color }}>
        <span className="tqm-hand" style={{ fontSize: 22, color: P.navy }}>{r.ok ? 'stamped!' : 'nope!'}</span>
        <span className="t">{r.ok ? 'RIDE' : 'NOT'}<br />VERIFIED</span>
        <span className="r">{r.from.name} → {r.to.name}</span>
        <span className="s">{r.line} Line{r.trip ? ` · trip ${r.trip.id}` : ''}</span>
      </div>
      {!!r.reward.points && <div className="tqm-burst"><i>+{r.reward.points}</i></div>}
      <div className="tqm-box" style={{ width: '100%', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div className="tqm-checks">
          {r.checks.map((c, i) => (
            <div key={i}>
              <b style={{ background: c.ok ? P.lgreen : c.soft ? '#fff' : P.pink }}>{c.ok ? '✓' : c.soft ? '–' : '✕'}</b><span>{c.text}</span>
            </div>
          ))}
        </div>
        {r.reward.note && <span className="tqm-src">{r.reward.note}</span>}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <button type="button" className="tqm-big" onClick={onClose}>Back to map</button>
          <a className="tqm-big yellow" href={traveledHref}>See Traveled</a>
        </div>
      </div>
    </div>
  );
}
