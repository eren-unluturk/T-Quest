// Mounts a map into the ported design markup (web/src/design/generated/*), whose map areas are static SVG art.
// Render <MapSlot> as a sibling of the markup inside the phone frame; it finds the art, covers it with a live map,
// and passes the frame element along so sheets can cover the whole phone.
import { useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';

/** Where the map goes: `art` is the static map SVG; `over` puts the map above the art's siblings too (pins, labels). */
export interface SlotTarget { art: (frame: HTMLElement) => Element | null; over: boolean }

/** Home (Main.dc.html): the 348x330 map card; the live map covers its static pins and label. */
export const HOME_MAP_CARD: SlotTarget = { art: (f) => f.querySelector('svg[width="348"][height="330"]'), over: true };
/** Traveled (Traveled.dc.html): the full-screen 390x844 map art; the legend, spot card and nav stay on top. */
export const TRAVELED_MAP: SlotTarget = { art: (f) => f.querySelector('svg[width="390"][height="844"]'), over: false };

export function MapSlot({ target, children }: { target: SlotTarget; children: (frame: HTMLElement) => ReactNode }) {
  const probe = useRef<HTMLSpanElement>(null);
  const [slot, setSlot] = useState<{ host: HTMLElement; frame: HTMLElement } | null>(null);
  useLayoutEffect(() => {
    const frame = probe.current?.parentElement;
    const art = frame && target.art(frame);
    if (!frame || !art?.parentElement) return;
    const host = document.createElement('div');
    host.style.cssText = `position:absolute;inset:0;${target.over ? 'z-index:4' : ''}`;
    if (target.over) art.parentElement.appendChild(host);
    else art.after(host);
    setSlot({ host, frame });
    return () => { host.remove(); setSlot(null); };
  }, [target]);
  return (
    <>
      <span ref={probe} hidden />
      {slot && createPortal(children(slot.frame), slot.host)}
    </>
  );
}
