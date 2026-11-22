import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { createApi } from './api/client';
import { Session } from './api/session';
import { AppProvider } from './app/app';
import { readConfig } from './config';
import './design/design.css';

const root = createRoot(document.getElementById('root')!);
const cfg = readConfig();

if ('missing' in cfg) {
  root.render(<p style={{ fontFamily: 'system-ui', padding: 16 }}>Not configured: set {cfg.missing.join(', ')} (see web/README.md).</p>);
} else {
  const session = new Session();
  const api = createApi(cfg, session);
  root.render(
    <StrictMode>
      <AppProvider value={{ api, session }}>
        <App />
      </AppProvider>
    </StrictMode>,
  );
}
