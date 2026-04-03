import path from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@wfc': path.resolve(__dirname, '../dungeon-wfc/src/engine'),
      '@wfc-utils': path.resolve(__dirname, '../dungeon-wfc/src/utils'),
    },
  },
  server: {
    port: 5200,
    open: true,
  },
  build: {
    outDir: 'dist',
  },
});
