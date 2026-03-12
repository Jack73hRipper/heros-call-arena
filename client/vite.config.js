import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Detect if building for Electron (production builds use relative paths)
const isElectronBuild = process.env.ELECTRON_BUILD === 'true';

export default defineConfig({
  plugins: [react()],
  // Use relative paths for Electron production builds (file:// protocol)
  base: isElectronBuild ? './' : '/',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    // Ensure assets use relative paths for Electron's file:// loading
    assetsDir: 'assets',
    outDir: 'dist',
  },
});
