import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    port: 3002,
    host: true,
  },
  build: {
    outDir: resolve(__dirname, '../frontend-dist'),
    emptyOutDir: true,
  },
});
