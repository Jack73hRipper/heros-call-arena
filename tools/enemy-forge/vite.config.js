import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5230,
    strictPort: true,
    open: true,
    proxy: {
      '/api': 'http://localhost:5231',
      '/spritesheet.png': 'http://localhost:5231',
    },
  },
  build: {
    outDir: 'dist',
  },
});
