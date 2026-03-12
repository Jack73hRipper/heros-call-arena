import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5210,
    strictPort: true,
    open: true,
    proxy: {
      '/api': 'http://localhost:5211',
    },
  },
  // Serve audio files from the main client/public/audio directory
  publicDir: false,
  resolve: {
    alias: {
      '@audio': path.resolve(__dirname, '../../client/public/audio'),
    },
  },
  build: {
    outDir: 'dist',
  },
});
