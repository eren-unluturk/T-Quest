import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Local development needs no CORS: the browser talks to this dev server and it forwards to the three backends.
// Override the targets with DEV_DP_URL / DEV_IS_URL / DEV_GE_URL if your services run elsewhere.
const target = (name: string, port: number) => process.env[name] ?? `http://127.0.0.1:${port}`;

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/dp': { target: target('DEV_DP_URL', 8001), changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/dp/, '') },
      '/api/is': { target: target('DEV_IS_URL', 8002), changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/is/, '') },
      '/api/ge': { target: target('DEV_GE_URL', 8003), changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/ge/, '') },
    },
  },
});
