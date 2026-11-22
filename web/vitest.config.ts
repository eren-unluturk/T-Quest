import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';
export default defineConfig({
  resolve: {
    alias: { '@tquest/map': fileURLToPath(new URL('../client-bryan/map/src/index.ts', import.meta.url)) },
    dedupe: ['react', 'react-dom', 'maplibre-gl'],
  },
  test: { environment: 'node', include: ['src/**/*.test.{ts,tsx}'] },
});
