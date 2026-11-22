// Shared pieces for the map overlays, and the MapLibre lifecycle hook.
import type { Map as MlMap, MapOptions } from 'maplibre-gl';
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { paintCanvas } from './layers';
import { BASEMAP, P } from './theme';

type MapLibre = typeof import('maplibre-gl');
let lib: MapLibre | null = null;
/** MapLibre, loaded on first use: importing it eagerly breaks pages and tests without WebGL or blob workers (jsdom). */
export const maplibre = (): MapLibre => {
  if (!lib) throw new Error('MapLibre is not loaded yet');
  return lib;
};

/** Creates a MapLibre map in `ref` once, paints the basemap, and removes it on unmount. `ready` flips when the style has loaded. */
export function useMapLibre(opts: Omit<MapOptions, 'container' | 'style'>) {
  const ref = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<MlMap | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string>();
  useEffect(() => {
    let live = true;
    let m: MlMap | null = null;
    import('maplibre-gl').then((mod) => {
      lib = ((mod as { default?: MapLibre }).default ?? mod) as MapLibre;
      if (!live || !ref.current) return;
      const created = new lib.Map({ ...opts, container: ref.current, style: BASEMAP });
      created.on('load', () => { paintCanvas(created); if (live) setReady(true); });
      m = created;
      setMap(created);
    }).catch((e: Error) => { if (live) setError(`the map could not start (${e.message})`); });
    return () => { live = false; setReady(false); setMap(null); m?.remove(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return { ref, map, ready, error };
}

/** Renders overlays (sheets, the stamp) into `target`, which should be the phone frame; inline when it is missing. */
export function Overlay({ target, children }: { target?: HTMLElement | null; children: ReactNode }) {
  const body = <div className="tqm-layer" style={{ position: 'absolute', inset: 0, zIndex: 50 }}>{children}</div>;
  return target ? createPortal(body, target) : body;
}

export function CloseButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" className="tqm-round" aria-label={label} onClick={onClick}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={P.navy} strokeWidth="3" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
    </button>
  );
}

export const Dot = ({ color, size = 12 }: { color: string; size?: number }) =>
  <span className="tqm-dot" style={{ background: color, width: size, height: size }} />;
