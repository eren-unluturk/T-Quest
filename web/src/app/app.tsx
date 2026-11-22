import { createContext, useCallback, useContext, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import type { Api } from '../api/client';
import { ApiError } from '../api/client';
import type { Session } from '../api/session';
import { DATA_CREDITS, FOOTER } from '../config';

export interface AppCtx { api: Api; session: Session }
const Ctx = createContext<AppCtx | null>(null);

export function AppProvider({ value, children }: { value: AppCtx; children: ReactNode }) {
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error('AppProvider missing');
  return c;
}

/** Re-renders when the session changes (login, logout, expiry). */
export function useSessionState() {
  const { session } = useApp();
  return useSyncExternalStore(
    (fn) => session.subscribe(fn),
    () => session.isLoggedIn(),
  );
}

export interface Async<T> { data: T | undefined; error: ApiError | Error | undefined; loading: boolean; reload: () => void }

/** Runs `fn` on mount and whenever `deps` change; ignores results from stale runs. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): Async<T> {
  const [state, setState] = useState<{ data?: T; error?: Error; loading: boolean }>({ loading: true });
  const [tick, setTick] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => {
    let live = true;
    setState((s) => ({ data: s.data, loading: true }));
    fnRef.current().then(
      (data) => live && setState({ data, loading: false }),
      (error: Error) => live && setState({ error, loading: false }),
    );
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data: state.data, error: state.error, loading: state.loading, reload };
}

/** Plain status box for loading and error states. The design has none, so this stays minimal and unstyled. */
export function Status({ loading, error, reload }: { loading: boolean; error?: Error; reload?: () => void }) {
  if (error) {
    return (
      <div role="alert" style={{ padding: 16, fontFamily: 'Inter, system-ui, sans-serif', color: '#1D3557' }}>
        <p style={{ margin: '0 0 8px' }}>{error.message}</p>
        {reload && <button type="button" onClick={reload}>Retry</button>}
      </div>
    );
  }
  if (loading) {
    return <div aria-busy="true" role="status" style={{ padding: 16, fontFamily: 'Inter, system-ui, sans-serif', color: '#457B9D' }}>…</div>;
  }
  return null;
}

/** Centers the design's 390x844 phone frame and adds the demo footer and credits under it. */
export function Frame({ children, credits = [], dark = false }: { children: ReactNode; credits?: string[]; dark?: boolean }) {
  return (
    <div style={{ minHeight: '100vh', background: dark ? '#14243c' : '#E9DFCB', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '16px 0 24px' }}>
      <div style={{ width: 390, minHeight: 844, position: 'relative', borderRadius: 24, overflow: 'hidden', boxShadow: '0 6px 24px rgba(0,0,0,.25)' }}>{children}</div>
      <footer style={{ width: 390, maxWidth: '100%', marginTop: 12, fontFamily: 'Inter, system-ui, sans-serif', fontSize: 12, color: '#1D3557', lineHeight: 1.45 }}>
        {credits.map((c) => <p key={c} style={{ margin: '0 0 4px' }}>{c}</p>)}
        <p style={{ margin: '0 0 4px', fontWeight: 700 }}>{FOOTER}</p>
        <p style={{ margin: 0, color: '#457B9D' }}>Data: {DATA_CREDITS.join('; ')}.</p>
      </footer>
    </div>
  );
}
