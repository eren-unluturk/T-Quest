// Home map: the GIS map of Isabella's Home screen.
// Recolored OSM basemap, real MBTA lines and stations, live trains, 3D landmarks from BPDA roofprints,
// the tap-in zone and ride verification, and the Ethnic Boston layer with T directions.
import type { GeoJSONSource, Marker } from 'maplibre-gl';
import { useEffect, useMemo, useRef, useState } from 'react';
import { DirectionsSheet, planDirections } from './Directions';
import type { DirectionsPlan } from './Directions';
import { loadGis, loadTransit, loadVehicles } from './data';
import type { Gis, MapServices, Transit, Vehicle } from './data';
import { circle, fc, nearest } from './geo';
import type { LatLon } from './geo';
import {
  addEthnic, addIconic, addLines, addStations, addVehicles, clearRoute, declutter, drawRoute, iconicPopup, setVehicles, showEthnic,
} from './layers';
import { RideSheet, Stamp, finishRide } from './Ride';
import type { RideOutcome, RideReward, VerifiedRide } from './Ride';
import { P } from './theme';
import { Overlay, maplibre, useMapLibre } from './ui';
import { ZONE_M } from './verify';
import type { Station } from './verify';

export interface MapPin { id: string; name: string; lat: number; lon: number; color?: string }

export interface HomeMapProps {
  services: MapServices;
  /** Where the rider is. Defaults to ~30 m from Park Street (the design's scene). */
  position?: LatLon;
  /** Demo: tapping empty map moves the rider there. */
  movable?: boolean;
  /** Spots to pin (station facts, nearby content). The selected one is drawn big and yellow. */
  pins?: MapPin[];
  selectedPin?: string;
  onPickPin?: (id: string) => void;
  /** The rider's nearest station changed. */
  onStation?: (s: Station & { d: number }) => void;
  /** A ride passed verification: record it (game-engine check-in) and report the points. */
  onRideVerified?: (ride: VerifiedRide) => Promise<RideReward | void>;
  /** Element the sheets and stamp cover (the phone frame). Defaults to the map card itself. */
  overlay?: HTMLElement | null;
  /** Ethnic Boston layer on/off. Uncontrolled (remembered in localStorage) when omitted. */
  ethnic?: boolean;
  onEthnicChange?: (on: boolean) => void;
  spotsHref?: string;
  traveledHref?: string;
}

const PARK_STREET = { lat: 42.35618, lon: -71.06212 };
const CITY_VIEW = { center: [-71.075, 42.322] as [number, number], zoom: 11.4, pitch: 25, bearing: 0 };
const ETHNIC_KEY = 'tq.ethnic';
const readEthnic = () => { try { return JSON.parse(localStorage.getItem(ETHNIC_KEY) ?? 'false') === true; } catch { return false; } };

export function HomeMap(props: HomeMapProps) {
  const { services, pins = [], selectedPin, overlay, movable = true } = props;
  const [data, setData] = useState<{ t: Transit; g: Gis } | null>(null);
  const [error, setError] = useState<string>();
  const [vehicles, setVehiclesState] = useState<Vehicle[]>([]);
  const [pos, setPos] = useState<LatLon>(props.position ?? PARK_STREET);
  const [ethnicLocal, setEthnicLocal] = useState(readEthnic);
  const ethnic = props.ethnic ?? ethnicLocal;
  const [plan, setPlan] = useState<DirectionsPlan | null>(null);
  const [riding, setRiding] = useState(false);
  const [stamp, setStamp] = useState<RideOutcome | null>(null);
  const [flat, setFlat] = useState(false);

  useEffect(() => { if (props.position) setPos(props.position); }, [props.position?.lat, props.position?.lon]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    let live = true;
    Promise.all([loadTransit(services), loadGis()]).then(([t, g]) => live && setData({ t, g }), (e: Error) => live && setError(e.message));
    const tick = () => loadVehicles(services).then((v) => live && setVehiclesState(v)).catch(() => {});
    tick();
    const id = setInterval(tick, 15000);
    return () => { live = false; clearInterval(id); };
  }, [services.dp, services.mbta]); // eslint-disable-line react-hooks/exhaustive-deps

  const station = useMemo(() => (data ? nearest(data.t.stations, pos) : null), [data, pos]);
  const { ref, map, ready, error: mapError } = useMapLibre({
    center: [pos.lon, pos.lat], zoom: 15.4, pitch: 50, bearing: -15, maxPitch: 70,
    attributionControl: { compact: true, customAttribution: 'BPDA · Boston Landmarks Commission · MBTA' },
  });

  // latest values for the map's click handler, which is registered once
  const live = useRef({ ethnic, station, data, movable });
  live.current = { ethnic, station, data, movable };

  // layers, once the style and the data are both in
  const [layered, setLayered] = useState(false);
  useEffect(() => {
    if (!map || !ready || !data || layered) return;
    addLines(map, data.t.shapes);
    addIconic(map, data.g);
    addVehicles(map, vehicles);
    addStations(map, data.t.stations);
    addEthnic(map, data.g, ethnic);
    map.addSource('zone', { type: 'geojson', data: fc([circle(station ?? pos, ZONE_M)]) });
    map.addLayer({ id: 'zone', type: 'line', source: 'zone', paint: { 'line-color': P.navy, 'line-width': 2, 'line-dasharray': [2, 2] } });
    if (ethnic) map.jumpTo(CITY_VIEW);
    map.on('click', (e) => {
      const cur = live.current;
      if (iconicPopup(map, e)) return;
      const hit = cur.ethnic && map.queryRenderedFeatures(e.point, { layers: ['ethnic-fill'] })[0];
      if (hit && cur.data && cur.station) {
        const hood = cur.data.g.ethnic.features.find((f) => f.properties.name === hit.properties.name);
        if (hood) setPlan(planDirections(cur.data.t.net, cur.data.t.stations, hood.properties, cur.station));
        return;
      }
      if (!cur.ethnic && cur.movable) setPos({ lat: e.lngLat.lat, lon: e.lngLat.lng });
    });
    setLayered(true);
  }, [map, ready, data]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (map && layered) setVehicles(map, vehicles); }, [map, layered, vehicles]);

  // the rider: blue dot, the tap-in zone around the nearest station, and a nudge to the host
  const you = useRef<Marker | null>(null);
  useEffect(() => {
    if (!map) return;
    if (!you.current) {
      const el = document.createElement('div');
      el.className = 'tqm-you';
      you.current = new (maplibre()).Marker({ element: el }).setLngLat([pos.lon, pos.lat]).addTo(map);
    } else you.current.setLngLat([pos.lon, pos.lat]);
    if (!layered || !station) return;
    (map.getSource('zone') as GeoJSONSource | undefined)?.setData(fc([circle(station, ZONE_M)]));
    if (!live.current.ethnic) map.easeTo({ center: [station.lon, station.lat], duration: 700 });
  }, [map, layered, pos, station?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => { you.current?.remove(); you.current = null; }, [map]);
  useEffect(() => { if (station) props.onStation?.(station); }, [station?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // spot pins, hidden while Ethnic Boston is on
  useEffect(() => {
    if (!map || ethnic) return;
    const sel = pins.findIndex((p) => p.id === selectedPin);
    const markers = pins.map((p, j) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'tqm-pin' + (j === sel ? ' sel' : '');
      b.style.background = p.color ?? P.pink;
      b.setAttribute('aria-label', p.name);
      b.setAttribute('aria-pressed', String(j === sel));
      b.innerHTML = '<i></i>';
      b.onclick = (e) => { e.stopPropagation(); props.onPickPin?.(p.id); };
      return new (maplibre()).Marker({ element: b }).setLngLat([p.lon, p.lat]).addTo(map);
    });
    const tidy = () => declutter(map, markers, sel, 34);
    map.on('moveend', tidy);
    tidy();
    return () => { map.off('moveend', tidy); markers.forEach((m) => m.remove()); };
  }, [map, ethnic, pins, selectedPin]); // eslint-disable-line react-hooks/exhaustive-deps

  const setEthnic = (on: boolean) => {
    if (props.ethnic === undefined) { setEthnicLocal(on); try { localStorage.setItem(ETHNIC_KEY, JSON.stringify(on)); } catch { /* private mode */ } }
    props.onEthnicChange?.(on);
  };
  const firstEthnic = useRef(true);
  useEffect(() => {
    if (!map || !layered) return;
    showEthnic(map, ethnic);
    if (firstEthnic.current) { firstEthnic.current = false; return; }
    clearRoute(map);
    const here = station ?? pos;
    map.easeTo(ethnic ? { ...CITY_VIEW, duration: 900 } : { center: [here.lon, here.lat], zoom: 15.4, pitch: 50, bearing: -15, duration: 900 });
  }, [map, layered, ethnic]); // eslint-disable-line react-hooks/exhaustive-deps

  const inside = !!station && station.d <= ZONE_M;
  const nameOf = (id: string) => data?.t.stations.find((s) => s.id === id)?.name ?? id;
  const stationOf = (id: string) => data?.t.stations.find((s) => s.id === id);

  return (
    <div className="tqm-root">
      <div ref={ref} className="tqm-canvas" />
      {(error || mapError) && <div className="tqm-box tqm-msg" role="alert">Map unavailable: {error ?? mapError}</div>}
      {!data && !error && !mapError && <div className="tqm-box tqm-msg" role="status">loading the T…</div>}
      {station && (
        <button type="button" className="tqm-tapin" disabled={!inside} onClick={() => setRiding(true)}>
          {inside ? `Tap in at ${station.name} →` : `${Math.round(station.d)} m to ${station.name}`}
        </button>
      )}
      <button type="button" className="tqm-tilt" aria-label="2D / 3D" onClick={() => {
        map?.easeTo({ pitch: flat ? 50 : 0, bearing: flat ? -15 : 0, duration: 700 });
        setFlat(!flat);
      }}>{flat ? '3D' : '2D'}</button>
      <button type="button" className={`tqm-ethnic${ethnic ? ' on' : ''}`} aria-pressed={ethnic} onClick={() => setEthnic(!ethnic)}>Ethnic Boston</button>
      <span className="tqm-label">{data?.t.mbtaError ? 'T lines offline, try again soon' : ethnic ? 'tap a neighborhood' : 'tap a spot to learn about it'}</span>

      {plan && station && data && (
        <Overlay target={overlay}>
          <DirectionsSheet plan={plan} from={station} net={data.t.net} nameOf={nameOf} spotsHref={props.spotsHref}
            onClose={() => setPlan(null)}
            onShow={() => { if (map && plan.route) drawRoute(map, data.t.shapes, stationOf, plan.route, plan.dest, plan.hub); setPlan(null); }} />
        </Overlay>
      )}
      {riding && station && data && (
        <Overlay target={overlay}>
          <RideSheet services={services} from={station} stations={data.t.stations} vehicles={vehicles}
            onClose={() => setRiding(false)}
            onDone={async (r) => {
              setRiding(false);
              const out = await finishRide(services, r, props.onRideVerified);
              if (out.ok) setPos({ lat: r.to.lat, lon: r.to.lon });
              setStamp(out);
            }} />
        </Overlay>
      )}
      {stamp && <Overlay target={overlay}><Stamp r={stamp} traveledHref={props.traveledHref} onClose={() => setStamp(null)} /></Overlay>}
    </div>
  );
}
