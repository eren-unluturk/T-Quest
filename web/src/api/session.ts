/**
 * In-memory session. The token is NEVER written to localStorage, sessionStorage or cookies: a page reload logs out.
 * That is deliberate for a public demo (nothing to steal from disk, nothing persists on shared machines).
 */
export interface SessionData {
  token: string;
  username: string;
  expiresAt: number; // epoch ms
}

type Listener = () => void;

export class Session {
  private data: SessionData | null = null;
  private listeners = new Set<Listener>();
  constructor(private now: () => number = () => Date.now()) {}

  set(token: string, username: string, expiresInS: number): void {
    this.data = { token, username, expiresAt: this.now() + Math.max(0, expiresInS) * 1000 };
    this.emit();
  }

  clear(): void {
    if (this.data) {
      this.data = null;
      this.emit();
    }
  }

  /** The token, or null when absent or expired (an expired token is dropped). */
  token(): string | null {
    if (!this.data) return null;
    if (this.now() >= this.data.expiresAt - 5000) {
      this.clear(); // treat a token within 5 s of expiry as expired
      return null;
    }
    return this.data.token;
  }

  username(): string | null {
    return this.token() ? this.data!.username : null;
  }

  isLoggedIn(): boolean {
    return this.token() !== null;
  }

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private emit() {
    this.listeners.forEach((l) => l());
  }
}
